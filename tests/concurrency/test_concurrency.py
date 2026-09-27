"""Concurrency tests for save endpoints.

Race conditions on:
  - PUT /api/events/<slug>/me/batch/<id>/scores        (scoring)
  - POST /api/events/<slug>/submissions/<id>/vote      (voting)
  - POST /api/events/<slug>/normalize                  (organizer)
  - GET /api/webhooks + POST /api/webhooks             (read during write)
  - POST /api/login                                    (session rotation)

We have one worker so Django's dev server is process-serial — but the
test client + the ORM both run concurrently when we fan out to a
thread pool, and the goal here is to catch naive patterns that would
break under a real concurrent load:

  * ``update_or_create`` must not duplicate rows on (assignment, criterion).
  * ``update_or_create`` must not corrupt the persisted ``value`` when two
    threads upsert different numbers for the same key.
  * The vote table's ``unique_together=(event, project, voter_key)`` must
    collapse duplicate ballots into one row.
  * The normalize endpoint is meant to be idempotent on the *body* but
    NOT idempotent on the *audit row* — two POSTs should produce two
    ``NormalizationRun`` rows that each reflect the same input.
  * A GET on /api/webhooks must not block behind a concurrent POST on
    /api/webhooks — they touch disjoint rows.
  * ``LoginView`` deletes existing sessions and creates a new one each
    call. Concurrent logins for the same user must each succeed and
    produce N distinct sessions, not silently lose writes.

Notes
-----
* ``ThreadPoolExecutor`` is the only sync concurrency primitive we use;
  no mocking of the lock manager.
* Each test uses ``pytest.mark.concurrency`` (already registered in
  ``pytest.ini``).
* We fan two requests out in parallel; "true" concurrency is bounded
  by the GIL and by the test client's in-process WSGI dispatch — the
  invariants we assert are valid under any reasonable interleaving.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Session
from apps.judging.assignment import run_assignment
from apps.judging.models import JudgeAssignment, Score
from apps.normalization.models import JudgeBias, NormalizationRun, NormalizedScore
from apps.submissions.models import Submission
from apps.voting.models import Vote, VoteAudit
from tests.concurrency.factories import (
    build_event_with_two_projects,
    build_judge_assignment_for,
    make_organizer_session,
    normalize_body,
)

pytestmark = pytest.mark.concurrency


User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _client_for(user) -> Client:
    """Return a Django test client with a fresh session cookie for ``user``."""
    token = _issue_session(user)
    c = Client()
    c.cookies["session"] = token
    return c


def _issue_session(user) -> str:
    """Mint a session token + persist the hashed row, return the plain token."""
    import hashlib
    import secrets

    token = secrets.token_urlsafe(32)
    Session.objects.create(
        user=user,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        label="concurrency",
        expires_at=timezone.now() + timedelta(days=1),
    )
    return token


def _run_in_threads(callables):
    """Run ``callables`` in parallel on a thread pool, return results in order.

    Each callable returns one result; exceptions are propagated. We close
    the per-thread DB connection at the end so pytest-django's
    transaction rollback isn't fighting open cursors.
    """
    results: list = [None] * len(callables)
    errors: list = [None] * len(callables)

    def _runner(idx, fn):
        try:
            results[idx] = fn()
        except Exception as exc:  # noqa: BLE001
            errors[idx] = exc
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(callables)) as pool:
        futures = [pool.submit(_runner, i, fn) for i, fn in enumerate(callables)]
        for f in as_completed(futures):
            f.result()

    for err in errors:
        if err is not None:
            raise err
    return results


def _fire_put_scores(client, slug, project_id, criterion, value):
    return client.put(
        f"/api/events/{slug}/me/batch/{project_id}/scores",
        data={"scores": [{"criterion_id": str(criterion.id), "value": value}]},
        content_type="application/json",
    )


def _fire_post_vote(client, slug, project_id, votes=1, remote_addr=None, ua=None):
    meta = {}
    if remote_addr:
        meta["REMOTE_ADDR"] = remote_addr
    if ua:
        meta["HTTP_USER_AGENT"] = ua
    return client.post(
        f"/api/events/{slug}/submissions/{project_id}/vote",
        data={"votes": votes},
        content_type="application/json",
        **meta,
    )


# ---------------------------------------------------------------------------
# Fixtures local to this test module
# ---------------------------------------------------------------------------


@pytest.fixture
def two_project_event(db, organizer, judge_a, judge_b, judge_c, participant):
    """Build an event with two teams / two submissions / three judges.

    Wider than ``sample_event``: needed for normalize (needs a connected
    bipartite) and for vote-different-voter tests (two distinct projects).
    """
    return build_event_with_two_projects(
        organizer=organizer,
        judges=[judge_a, judge_b, judge_c],
    )


@pytest.fixture
def two_project_event_first_project(two_project_event):
    """The first submission of the two-project event.

    Many race tests need a stable target project to score / vote against.
    """
    return two_project_event.submissions.order_by("created_at").first()


@pytest.fixture
def assigned_judge_a(db, two_project_event, judge_a, two_project_event_first_project):
    """A ``JudgeAssignment`` for ``judge_a`` on the first project."""
    return build_judge_assignment_for(
        event=two_project_event,
        judge=judge_a,
        project=two_project_event_first_project,
    )


@pytest.fixture
def criterion_innovation(two_project_event):
    """First rubric criterion (Innovation) of the two-project event."""
    return two_project_event.rubric.criteria.first()


# ---------------------------------------------------------------------------
# 1. Concurrent score-save: same judge, same criterion, two PUTs.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_score_save_creates_one_row(
    assigned_judge_a,
    criterion_innovation,
    judge_a,
    two_project_event,
):
    """Two PUTs from the same judge for the same criterion must yield
    exactly one ``Score`` row.

    ``Score.objects.update_or_create`` keys on
    ``unique_together=(assignment, criterion)``; the upsert must
    serialize the two writes into a single persisted row.
    """
    client = _client_for(judge_a)
    slug = two_project_event.slug
    project_id = str(assigned_judge_a.project_id)

    def put_high():
        return _fire_put_scores(client, slug, project_id, criterion_innovation, 5)

    def put_low():
        return _fire_put_scores(client, slug, project_id, criterion_innovation, 1)

    responses = _run_in_threads([put_high, put_low])
    assert all(r.status_code == 200 for r in responses)

    rows = Score.objects.filter(assignment=assigned_judge_a, criterion=criterion_innovation)
    assert rows.count() == 1, (
        f"Expected exactly one Score row, got {rows.count()}: " f"{list(rows.values('value', 'updated_at'))}"
    )


# ---------------------------------------------------------------------------
# 2. Last-write-wins: value must be one of the two we wrote, not garbage.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_score_save_last_write_wins(
    assigned_judge_a,
    criterion_innovation,
    judge_a,
    two_project_event,
):
    """The persisted ``value`` after two concurrent PUTs must equal one of
    the two we sent (5 or 1), never a blend or a default."""
    client = _client_for(judge_a)
    slug = two_project_event.slug
    project_id = str(assigned_judge_a.project_id)

    responses = _run_in_threads(
        [
            lambda: _fire_put_scores(client, slug, project_id, criterion_innovation, 5),
            lambda: _fire_put_scores(client, slug, project_id, criterion_innovation, 1),
        ]
    )
    assert all(r.status_code == 200 for r in responses)

    score = Score.objects.get(assignment=assigned_judge_a, criterion=criterion_innovation)
    assert score.value in (1, 5), f"Expected last-write-wins (1 or 5), got {score.value!r}"


# ---------------------------------------------------------------------------
# 3. Concurrent vote from the same voter_key (anonymous fingerprint).
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_vote_same_voter_key_collapses(two_project_event, two_project_event_first_project):
    """Two POSTs to /vote with the same IP + UA fingerprint must produce
    a single ``Vote`` row (the ``unique_together`` on
    ``(event, project, voter_key)`` collapses them)."""
    client = Client()  # anonymous
    slug = two_project_event.slug
    project_id = str(two_project_event_first_project.id)

    # Same fingerprint in both calls.
    def first():
        return _fire_post_vote(
            client,
            slug,
            project_id,
            votes=1,
            remote_addr="10.0.0.1",
            ua="ua-A",
        )

    def second():
        # Different client instance, same fingerprint.
        c = Client()
        return _fire_post_vote(
            c,
            slug,
            project_id,
            votes=1,
            remote_addr="10.0.0.1",
            ua="ua-A",
        )

    responses = _run_in_threads([first, second])
    assert all(r.status_code == 201 for r in responses)

    rows = Vote.objects.filter(
        event=two_project_event,
        project=two_project_event_first_project,
    )
    assert rows.count() == 1, f"Expected one Vote row, got {rows.count()}"
    assert rows.first().votes == 1
    assert VoteAudit.objects.filter(vote=rows.first(), action="cast").count() == 2


# ---------------------------------------------------------------------------
# 4. Concurrent vote from different voter_keys.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_vote_different_voter_keys_creates_two_rows(two_project_event, two_project_event_first_project):
    """Two POSTs with different fingerprints must produce two distinct
    ``Vote`` rows — one per voter."""
    slug = two_project_event.slug
    project_id = str(two_project_event_first_project.id)

    def voter_one():
        c = Client()
        return _fire_post_vote(
            c,
            slug,
            project_id,
            votes=1,
            remote_addr="10.0.0.1",
            ua="ua-one",
        )

    def voter_two():
        c = Client()
        return _fire_post_vote(
            c,
            slug,
            project_id,
            votes=1,
            remote_addr="10.0.0.2",
            ua="ua-two",
        )

    responses = _run_in_threads([voter_one, voter_two])
    assert all(r.status_code == 201 for r in responses)

    rows = Vote.objects.filter(
        event=two_project_event,
        project=two_project_event_first_project,
    )
    assert rows.count() == 2, f"Expected two Vote rows (distinct voter_keys), got {rows.count()}"
    keys = {r.voter_key for r in rows}
    assert len(keys) == 2, f"Expected distinct voter_keys, got {keys!r}"


# ---------------------------------------------------------------------------
# 5. Idempotent normalize POST.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_normalize_two_posts_each_internally_consistent(
    two_project_event,
    assigned_judge_a,
    criterion_innovation,
    judge_a,
    judge_b,
    judge_c,
):
    """Two POSTs to /api/events/<slug>/normalize with the same body must
    produce two ``NormalizationRun`` rows. Each row must be internally
    consistent — the score count, judge count, and audit-log payload
    must match between runs (same input -> same numbers)."""
    # Set up a fully-connected bipartite so the additive fit converges:
    # judge_a scores project_0, judge_b scores project_0 + project_1,
    # judge_c scores project_1.
    main = two_project_event.tracks.get(slug="main")
    submissions = list(Submission.objects.filter(event=two_project_event).order_by("name"))
    assert len(submissions) >= 2, "Need two submissions for this test"

    project_0, project_1 = submissions[0], submissions[1]
    rubric = two_project_event.rubric
    criteria = list(rubric.criteria.all())
    assert criteria, "Rubric must have at least one criterion"

    # Run the assignment algorithm with a 2x2 grid.
    batch_result = run_assignment(
        event=two_project_event,
        seed=99,
        reviews_per_project=2,
        projects_per_judge=2,
        created_by=judge_a,
    )
    JudgeAssignment.objects.filter(batch_id=batch_result["batch_id"]).count()

    # Save scores for every (judge, project, criterion) pair so the
    # bipartite graph is connected.
    for assignment in JudgeAssignment.objects.filter(batch_id=batch_result["batch_id"]):
        for crit in criteria:
            Score.objects.update_or_create(
                assignment=assignment,
                criterion=crit,
                defaults={"value": 4},
            )

    organizer_client = make_organizer_session(two_project_event)

    body = normalize_body(two_project_event.slug)

    def post_normalize():
        return organizer_client.post(
            f"/api/events/{two_project_event.slug}/normalize",
            data=body,
            content_type="application/json",
        )

    responses = _run_in_threads([post_normalize, post_normalize])
    assert all(r.status_code == 201 for r in responses), (
        f"Expected 201, got {[r.status_code for r in responses]}: " f"{[r.content for r in responses]}"
    )

    runs = list(NormalizationRun.objects.filter(event=two_project_event).order_by("created_at"))
    assert len(runs) == 2, f"Expected two NormalizationRun rows, got {len(runs)}"
    run_a, run_b = runs

    # Internal consistency: each run's per-row counts match its
    # NormalizedScore / JudgeBias row counts, and the calibration math
    # produced identical numbers (same input -> same fit).
    assert NormalizedScore.objects.filter(run=run_a).count() == run_a.n_projects
    assert NormalizedScore.objects.filter(run=run_b).count() == run_b.n_projects
    assert JudgeBias.objects.filter(run=run_a).count() == run_a.n_judges
    assert JudgeBias.objects.filter(run=run_b).count() == run_b.n_judges

    assert run_a.raw_sigma == run_b.raw_sigma
    assert run_a.normalized_sigma == run_b.normalized_sigma
    assert run_a.n_reviews == run_b.n_reviews
    assert run_a.n_projects == run_b.n_projects
    assert run_a.n_judges == run_b.n_judges
    assert run_a.is_connected is True and run_b.is_connected is True


# ---------------------------------------------------------------------------
# 6. Webhook GET during a POST.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_webhook_get_during_post_returns_200(two_project_event, organizer):
    """A GET on /api/webhooks running concurrently with a POST on the
    same endpoint must still return 200 — the GET does not block on the
    POST's INSERT (different rows, disjoint locks)."""
    list_client = make_organizer_session(two_project_event, label="organizer")

    def do_get():
        return list_client.get("/api/webhooks")

    def do_post():
        return list_client.post(
            "/api/webhooks",
            data={
                "event_slug": two_project_event.slug,
                "url": "https://example.invalid/hook",
                "events": ["score.submitted"],
            },
            content_type="application/json",
        )

    responses = _run_in_threads([do_get, do_post])
    get_resp, post_resp = responses
    assert get_resp.status_code == 200, (
        f"GET blocked during POST: status={get_resp.status_code}, " f"body={get_resp.content!r}"
    )
    assert post_resp.status_code == 201, f"POST failed: status={post_resp.status_code}, " f"body={post_resp.content!r}"


# ---------------------------------------------------------------------------
# 7. Session rotation under load.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_logins_create_n_sessions(participant):
    """N concurrent logins for the same user produce N sessions; older
    sessions remain valid until expiry (LoginView deletes prior rows
    before inserting a new one, but each new insert uses a fresh
    token so they don't collide on the unique ``token_hash``)."""
    from apps.accounts.models import User as _User  # noqa: F401

    email = participant.email
    password = "dogfood-dev-password"

    def do_login():
        c = Client()
        return c.post(
            "/api/login",
            data={"email": email, "password": password},
            content_type="application/json",
        )

    n = 5
    responses = _run_in_threads([do_login for _ in range(n)])
    assert all(r.status_code == 200 for r in responses), f"Some logins failed: {[r.status_code for r in responses]}"

    # LoginView deletes prior sessions before each insert. N logins => N
    # rows remaining (the last login's delete sweeps the others, then N
    # distinct inserts each land a fresh token_hash).
    sessions = Session.objects.filter(user=participant)
    assert sessions.count() == n, f"Expected {n} sessions after {n} logins, got {sessions.count()}"
    assert sessions.values("token_hash").distinct().count() == n, "Sessions must have distinct token_hash values"

    # The session cookie issued by each login round-trip must be
    # accepted by /api/me.
    me_responses = []
    for resp in responses:
        token = resp.cookies["session"].value
        c = Client()
        c.cookies["session"] = token
        me_responses.append(c.get("/api/me"))
    assert all(r.status_code == 200 for r in me_responses), (
        f"Some issued cookies failed /api/me: " f"{[r.status_code for r in me_responses]}"
    )
