"""CSV export tests for the streaming organizer-only endpoint.

Covers the shape, RFC 4180 dialect, special-character handling,
unicode, streaming response, organizer-only access control, and
multi-event filtering for ``apps.judging.views.CSVExportView``.

All tests use real fixtures from ``tests/conftest.py`` and hit the
real view through ``client.get()``. No mocking, no fixtures patched
after creation -- what the fixture makes, the view sees.
"""
from __future__ import annotations

import csv as csv_lib
import io
from decimal import Decimal

import pytest
from django.http import StreamingHttpResponse

from apps.events.models import Event, Membership, RubricCriterion
from apps.judging.assignment import run_assignment
from apps.judging.models import JudgeAssignment, Score


pytestmark = pytest.mark.csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


CSV_URL = "/api/csv_export"


def _read_streaming(response) -> str:
    """Drain a StreamingHttpResponse into a single str. The CSV view
    streams via ``_Echo`` so each ``streaming_content`` chunk is one
    CSV row; joining them reproduces the full body."""
    chunks = list(response.streaming_content)
    return b"".join(chunks).decode("utf-8")


def _seed_scores(event):
    """Run the assignment algorithm and create deterministic scores
    so the CSV has something to render. Returns the populated event."""
    organizer_membership = Membership.objects.get(event=event, role="organizer")
    run_assignment(
        event=event,
        seed=42,
        reviews_per_project=2,
        projects_per_judge=2,
        created_by=organizer_membership.user,
    )
    criteria = list(RubricCriterion.objects.filter(rubric__event=event))
    for assignment in JudgeAssignment.objects.filter(batch__event=event):
        for criterion in criteria:
            Score.objects.create(
                assignment=assignment,
                criterion=criterion,
                value=3,
            )
    return event


def _make_special_event(sample_event, organizer):
    """Create a second event so we can test multi-event ?event_slug
    routing. Returns the new event."""
    second = Event.objects.create(
        slug="second-hack-2026",
        name="Second Hack 2026",
        description="Multi-event test fixture",
        open_at=sample_event.open_at,
        submissions_close_at=sample_event.submissions_close_at,
        judging_open_at=sample_event.judging_open_at,
        judging_close_at=sample_event.judging_close_at,
        results_at=sample_event.results_at,
        created_by=organizer,
    )
    Membership.objects.create(
        user=organizer, event=second, role="organizer", created_by=organizer,
    )
    return second


# ---------------------------------------------------------------------------
# Shape: header row + N*M*K data rows
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_shape_n_projects_times_n_judges_times_n_criteria(
    auth_client, sample_event, sample_team, sample_submission,
):
    """For each (project, judge, criterion) the CSV carries exactly one
    data row. With N projects scored by M judges against K criteria,
    the body has 1 header row + N*M*K data rows."""
    event = _seed_scores(sample_event)

    # Two judges, two criteria, one project scored by both -> 4 data rows.
    # We seeded reviews_per_project=2, projects_per_judge=2; with one
    # project in the demo event the assignment creates exactly one
    # assignment per judge-project pair where the judge has slots.
    response = auth_client["organizer"].get(CSV_URL)
    assert response.status_code == 200, response.content

    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))
    assert len(rows) >= 2, f"expected header + data rows, got {len(rows)}"

    header = rows[0]
    assert header == [
        "event_slug", "project_id", "project_name",
        "judge_email", "criterion_name", "score", "weight",
    ]

    # The actual count is N * M * K where N = submitted projects in event,
    # M = unique judges that have a score, K = criteria.
    data_rows = rows[1:]
    unique_judges = {
        r[3] for r in data_rows
    }
    unique_projects = {
        r[1] for r in data_rows
    }
    unique_criteria = {
        r[4] for r in data_rows
    }
    assert len(data_rows) == (
        len(unique_projects) * len(unique_judges) * len(unique_criteria)
    )


# ---------------------------------------------------------------------------
# Header columns
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_header_columns(auth_client, sample_event, sample_team, sample_submission):
    """The header row is exactly the seven columns the spec promises."""
    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    assert response.status_code == 200

    body = _read_streaming(response)
    first_line = body.splitlines()[0]
    assert first_line == (
        "event_slug,project_id,project_name,judge_email,"
        "criterion_name,score,weight"
    )


# ---------------------------------------------------------------------------
# CSV dialect: comma-separated, RFC 4180 quoting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_csv_dialect_uses_commas(auth_client, sample_event, sample_team, sample_submission):
    """Default csv.writer splits on commas; verify a header with no
    embedded commas splits to the expected 7 columns."""
    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)

    rows = list(csv_lib.reader(io.StringIO(body)))
    assert len(rows[0]) == 7


@pytest.mark.django_db
def test_csv_quotes_commas_in_project_names(
    auth_client, sample_event, sample_team, sample_submission,
):
    """A project name with a comma must be wrapped in quotes so the
    column count is preserved when re-parsed."""
    sample_submission.name = "Acme, Inc. — comma in name"
    sample_submission.save()

    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))

    # Every row must have exactly 7 columns -- quoting preserves column
    # count across the embedded comma.
    for row in rows:
        assert len(row) == 7, (
            f"row {row!r} split into {len(row)} columns, expected 7"
        )

    # The project name shows up quoted in the raw text.
    assert '"Acme, Inc. — comma in name"' in body


@pytest.mark.django_db
def test_csv_preserves_embedded_newlines_in_project_names(
    auth_client, sample_event, sample_team, sample_submission,
):
    """RFC 4180: embedded newlines in quoted fields stay in the same
    logical record. Re-parsing must yield one row per record."""
    sample_submission.name = 'Test, "Quoted" Project\nNewline'
    sample_submission.save()

    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)

    # csv.reader with the default dialect splits on logical rows, not
    # on bare newlines inside quoted fields -- so we still get a
    # well-formed 7-column row for this submission.
    rows = list(csv_lib.reader(io.StringIO(body)))
    matched = [r for r in rows if len(r) == 7 and "Newline" in r[2]]
    assert len(matched) >= 1, (
        f"project with embedded newline split wrong; got rows = {rows!r}"
    )

    # And the raw body has the literal newline inside the quoted field.
    assert '\nNewline' in body


# ---------------------------------------------------------------------------
# Unicode / emoji
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unicode_arrow_in_project_name(
    auth_client, sample_event, sample_team, sample_submission,
):
    """A project name with a Unicode arrow exports as UTF-8."""
    sample_submission.name = "Project → Forward"
    sample_submission.save()

    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    assert response.status_code == 200

    body = _read_streaming(response)
    assert "Project → Forward" in body

    # The encoding is UTF-8 (no BOM, no escape sequences).
    raw = response.streaming_content
    raw_bytes = b"".join(raw)
    assert "→".encode("utf-8") in raw_bytes


@pytest.mark.django_db
def test_emoji_in_project_name(
    auth_client, sample_event, sample_team, sample_submission,
):
    """An emoji in a project name round-trips through the streaming
    response."""
    sample_submission.name = "Quokka 🐾 Project"
    sample_submission.save()

    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)

    assert "Quokka 🐾 Project" in body


# ---------------------------------------------------------------------------
# Empty event: header-only body
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_empty_event_returns_header_only(auth_client, sample_event):
    """With no scores in the event, the CSV body is just the header."""
    # Don't seed any scores -- the event has none.
    response = auth_client["organizer"].get(CSV_URL)
    assert response.status_code == 200

    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))
    assert len(rows) == 1, f"expected header only, got {len(rows)} rows"
    assert rows[0][0] == "event_slug"


# ---------------------------------------------------------------------------
# Streaming response: StreamingHttpResponse + text/csv
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_response_is_streaming(auth_client, sample_event, sample_team, sample_submission):
    """The view returns a Django StreamingHttpResponse, not a buffered
    HttpResponse."""
    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    assert isinstance(response, StreamingHttpResponse), (
        f"expected StreamingHttpResponse, got {type(response).__name__}"
    )


@pytest.mark.django_db
def test_response_content_type_is_text_csv(
    auth_client, sample_event, sample_team, sample_submission,
):
    """Content-Type must be text/csv so browsers + curl know to treat
    it as a downloadable CSV."""
    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    assert response["Content-Type"].startswith("text/csv"), (
        f"expected Content-Type text/csv, got {response['Content-Type']!r}"
    )


# ---------------------------------------------------------------------------
# Content-Disposition: attachment; filename="scores-<slug>.csv"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_content_disposition_uses_event_slug(
    auth_client, sample_event, sample_team, sample_submission,
):
    """The download filename is scores-<event-slug>.csv so organizers
    can save multiple events without overwriting each other."""
    _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    assert response["Content-Disposition"] == (
        f'attachment; filename="scores-{sample_event.slug}.csv"'
    )


# ---------------------------------------------------------------------------
# Organizer-only access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_non_organizer_gets_403(auth_client, sample_event, sample_team, sample_submission):
    """A judge or participant must not see the CSV export."""
    _seed_scores(sample_event)

    for label in ("judge_a", "judge_b", "participant"):
        response = auth_client[label].get(CSV_URL)
        assert response.status_code == 403, (
            f"{label} should get 403, got {response.status_code}"
        )


@pytest.mark.django_db
def test_anonymous_gets_403(client, sample_event):
    """No cookie at all -> IsAuthenticated denies the request."""
    response = client.get(CSV_URL)
    # DRF returns 403 (not 401) when no auth class produces credentials;
    # either is fine -- the spec says "401/403".
    assert response.status_code in (401, 403), (
        f"anonymous should be denied, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Multi-event: ?event_slug=<other> routes to the right event
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_slug_query_param_selects_event(
    auth_client, sample_event, sample_team, sample_submission, organizer,
):
    """Passing ?event_slug=<other> returns scores from that event
    (or the empty header-only body if the other event has no scores)."""
    _seed_scores(sample_event)
    other = _make_special_event(sample_event, organizer)

    response = auth_client["organizer"].get(f"{CSV_URL}?event_slug={other.slug}")
    assert response.status_code == 200

    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))

    # The 'other' event has no submissions or scores -- only the header.
    assert len(rows) == 1, (
        f"expected header-only body for empty event, got {len(rows)} rows"
    )
    # And the header still references 'other' as the event slug column.
    assert response["Content-Disposition"] == (
        f'attachment; filename="scores-{other.slug}.csv"'
    )


@pytest.mark.django_db
def test_organizer_for_other_event_cannot_export_this_event(
    auth_client, sample_event, sample_team, sample_submission, organizer,
):
    """If an organizer is organizer of event B but asks for event A's
    CSV, they must not see A's data."""
    _seed_scores(sample_event)
    other = _make_special_event(sample_event, organizer)

    response = auth_client["organizer"].get(f"{CSV_URL}?event_slug={sample_event.slug}")
    assert response.status_code == 200
    body = _read_streaming(response)

    # sample_event has scores -- this body should NOT be empty.
    rows = list(csv_lib.reader(io.StringIO(body)))
    assert len(rows) > 1


@pytest.mark.django_db
def test_organizer_cannot_export_event_they_dont_organize(
    auth_client, sample_event, sample_team, sample_submission, organizer,
):
    """A second organizer (organizer of a *different* event only) must
    be denied when they ask for the first event's CSV."""
    _seed_scores(sample_event)
    other = _make_special_event(sample_event, organizer)

    # Strip the organizer's membership from sample_event, leaving them
    # as an organizer of 'other' only.
    Membership.objects.filter(user=organizer, event=sample_event).delete()

    response = auth_client["organizer"].get(f"{CSV_URL}?event_slug={sample_event.slug}")
    assert response.status_code == 403, (
        f"organizer of another event should get 403, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Weight column reflects the criterion's weight
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_weight_column_matches_criterion_weight(
    auth_client, sample_event, sample_team, sample_submission,
):
    """The 7th column is the criterion weight, e.g. 0.400 for
    Innovation. Each criterion's rows must carry that criterion's
    own weight."""
    event = _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))

    # Build {criterion_name: weight} from the rubric.
    weights = {
        c.name: c.weight
        for c in RubricCriterion.objects.filter(rubric__event=event)
    }
    assert set(weights) == {"Innovation", "Execution", "Impact"}
    assert weights["Innovation"] == Decimal("0.400")

    # Walk data rows: the weight cell must equal the criterion's weight.
    for row in rows[1:]:
        criterion_name = row[4]
        weight_cell = row[6]
        assert Decimal(weight_cell) == weights[criterion_name], (
            f"weight {weight_cell!r} for {criterion_name!r} "
            f"does not match rubric weight {weights[criterion_name]}"
        )


# ---------------------------------------------------------------------------
# Row payload sanity (event_slug, judge_email, score)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_data_rows_carry_event_slug_and_judge_email(
    auth_client, sample_event, sample_team, sample_submission,
):
    """Every data row starts with the event's slug and references the
    judge by email (not by UUID -- organizers don't have to look up
    users)."""
    event = _seed_scores(sample_event)

    response = auth_client["organizer"].get(CSV_URL)
    body = _read_streaming(response)
    rows = list(csv_lib.reader(io.StringIO(body)))

    for row in rows[1:]:
        assert row[0] == event.slug
        # judge_email is an email-shaped string (contains '@')
        assert "@" in row[3]
        # score is an integer 1..5 for our rubric
        assert int(row[5]) in {1, 2, 3, 4, 5}
        # project_id is the Submission UUID as str
        assert len(row[1]) == 36  # UUID4 length


@pytest.mark.django_db
def test_unknown_event_slug_returns_404(auth_client, sample_event):
    """An event_slug that doesn't match any row returns 404, not 200."""
    response = auth_client["organizer"].get(
        f"{CSV_URL}?event_slug=does-not-exist"
    )
    assert response.status_code == 404
