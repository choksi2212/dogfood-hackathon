"""Build a fixtures.json-shaped export of an event (T4 bulk export).

The shape is EXACTLY what ``import_fixtures`` (and therefore
``POST /api/events/<slug>/import``) consumes, which makes the acceptance
property provable end to end:

    import fixtures.json -> export A -> re-import A -> export B
    => A and B are byte-identical.

That only works because every emitted field is derived from data the
importer restores verbatim, so the exporter is obsessed with
deterministic ordering and fixture-style ids:

* ids          trk_01.., jdg_01.., tm_01.., prj_01.. are assigned by
               stable sort order (Track.order, judge email, team name,
               team name + project name) — never by row UUIDs, which the
               importer re-randomizes on every run.
* ordering     every list is sorted by values that survive a re-import
               (names/emails/titles), never by timestamps or PKs.

Documented round-trip caveats (all outside the acceptance path of an
importer-seeded event):

* criteria keys outside the importer's standard rubric
  (functionality / quality / innovation) are dropped on re-import —
  the importer rebuilds the rubric from its own CRITERIA constant.
* a team with zero members gains a synthetic captain on re-import
  (import_fixtures synthesizes ``<team id>@test.local``); every
  importer-created team has >= 1 member, so this never fires in the
  round trip.
* the synthetic demo participant's team membership
  (``participant@test.local``, seeded by import_fixtures into the first
  fixture team for the acceptance suite) is NOT exported — the importer
  re-seeds it into the *first team in file order*, which after one
  round trip may be a different team, so exporting it would break the
  A == B property instead of preserving it.
* a project submitted twice by the same team (fixtures.json itself does
  this with prj_07/prj_41) is stored once (Submission is OneToOne with
  Team), so exports carry N-1 projects. Export A already reflects that,
  and A == B still holds.
* draft submissions are not exported (submitted_at is None, which the
  importer could not re-import) — the export covers the event's
  submitted surface, same as the gallery.
"""

import json

from django.utils.text import slugify

from apps.accounts.models import User
from apps.submissions.models import Submission
from apps.teams.models import TeamMember

# Mirrors the synthetic member import_fixtures._ensure_participant adds
# on every run (see the module docstring for why it is excluded here).
DEMO_PARTICIPANT_EMAIL = "participant@test.local"


def build_export(event) -> dict:
    """Assemble the fixtures-shaped dict for ``event``.

    Deterministic order everywhere (see module docstring): the same
    database always produces the same bytes.
    """
    tracks = list(event.tracks.order_by("order", "name"))
    track_ids = {t.id: f"trk_{i:02d}" for i, t in enumerate(tracks, start=1)}

    judges = list(
        User.objects.filter(memberships__event=event, memberships__role="judge").order_by("email")
    )
    judge_ids = {j.id: f"jdg_{i:02d}" for i, j in enumerate(judges, start=1)}

    # Sort teams by values the export ITSELF carries — name plus the
    # member email list — never by row ids/timestamps. This matters more
    # than it looks: the official fixtures.json contains DUPLICATE team
    # names (StillTrail x3, AmberSwitch x2, OpenSignal x2); the importer
    # keeps those rows apart only because their distinct captains are
    # part of its update_or_create lookup. Ordering by name alone would
    # leave the ties to the database's whim, and two exports of the same
    # content would disagree on which duplicate got tm_11 and which got
    # tm_12 — breaking A == B. The member list is import-stable (the
    # importer rebuilds memberships from exactly these emails), so
    # (name, members) orders the ties deterministically.
    teams = list(event.teams.all())
    team_members = {t.id: _team_member_emails(t) for t in teams}
    teams.sort(key=lambda t: (t.name, team_members[t.id]))
    team_ids = {t.id: f"tm_{i:02d}" for i, t in enumerate(teams, start=1)}

    # Projects sort inside that (import-stable) team order; team name
    # alone would be ambiguous for same-named teams.
    submissions = list(
        Submission.objects.filter(event=event, status="submitted").select_related("team", "track")
    )
    submissions.sort(key=lambda s: (s.team.name, team_members[s.team_id], s.name))
    project_ids = {s.id: f"prj_{i:02d}" for i, s in enumerate(submissions, start=1)}

    return {
        "event": {
            # The importer ignores fixture event ids (it keys events by
            # slug), but the id must still survive a re-import into a
            # *different* slug for the A == B round trip to hold — a
            # slug-derived id would change with the slug. The event NAME
            # is the one event field the importer restores verbatim, so
            # the id is derived from it (and stays self-describing for
            # humans reading the file).
            "id": f"evt_{slugify(event.name)}",
            "name": event.name,
            "submissions_close": event.submissions_close_at.isoformat(),
        },
        "tracks": [{"id": track_ids[t.id], "name": t.name} for t in tracks],
        "judges": [
            {"id": judge_ids[j.id], "name": j.name, "email": j.email, "tracks": []} for j in judges
        ],
        "teams": [
            {"id": team_ids[t.id], "name": t.name, "members": team_members[t.id]} for t in teams
        ],
        "projects": [
            {
                "id": project_ids[s.id],
                "team": team_ids[s.team_id],
                "track": track_ids[s.track_id],
                "title": s.name,
                "summary": s.tagline,
                "repo_url": s.repo_url,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            }
            for s in submissions
        ],
        "scores": _score_rows(event, judge_ids, project_ids, team_members),
    }


def _team_member_emails(team) -> list[str]:
    """The team's member emails, email-sorted, demo participant excluded
    (see the module docstring and DEMO_PARTICIPANT_EMAIL for why)."""
    return list(
        TeamMember.objects.filter(team=team)
        .exclude(user__email=DEMO_PARTICIPANT_EMAIL)
        .order_by("user__email")
        .values_list("user__email", flat=True)
    )


def _score_rows(event, judge_ids, project_ids, team_members):
    """One row per (judge, project) actually holding scores.

    Latest batch wins — the same rule the judging views apply
    (MyBatchView/ScoreSaveView resolve the newest batch): a judge can
    appear in several batches across the event's life, and emitting two
    rows for one (judge, project) would collapse on re-import (the
    importer get_or_creates by batch+judge+project), breaking A == B.

    Rows sort by (judge email, team name, member emails, project name)
    — every component is a value the export itself carries, so the
    ordering is identical in any database. Team name alone is not
    enough: the official fixtures contain duplicate team names
    (StillTrail x3, AmberSwitch x2, OpenSignal x2) whose tie order
    would otherwise depend on insertion order.
    """
    from apps.judging.models import JudgeAssignment, Score

    assignments = (
        JudgeAssignment.objects.filter(batch__event=event)
        .select_related("judge", "project__team", "review")
        .order_by("-batch__created_at", "id")
    )
    seen = set()
    rows = []
    for assignment in assignments:
        key = (assignment.judge_id, assignment.project_id)
        if key in seen:
            continue
        seen.add(key)
        if assignment.judge_id not in judge_ids or assignment.project_id not in project_ids:
            # Score rows for a demoted judge or a draft/withdrawn project
            # would be silently dropped by the importer on re-import
            # anyway — exclude them here so A == B holds.
            continue
        criteria = {}
        for score in (
            Score.objects.filter(assignment=assignment)
            .select_related("criterion")
            .order_by("criterion__order", "criterion__name")
        ):
            # Lowercased criterion name matches the key the importer
            # maps fixture criteria by (functionality / quality /
            # innovation). Non-standard rubric keys survive in A but are
            # dropped on re-import — documented caveat, not the
            # acceptance path.
            criteria[score.criterion.name.lower()] = score.value
        rows.append(
            (
                assignment.judge.email,
                assignment.project.team.name,
                team_members[assignment.project.team_id],
                assignment.project.name,
                {
                    "judge": judge_ids[assignment.judge_id],
                    "project": project_ids[assignment.project_id],
                    "criteria": criteria,
                    "comment": assignment.review.comment if hasattr(assignment, "review") else "",
                },
            )
        )
    rows.sort(key=lambda r: r[:4])
    return [r[4] for r in rows]


def chunked_export_json(export: dict):
    """Yield the export JSON one section (and, inside the big lists, one
    row) at a time, so the view can stream it without building a second
    full copy of the document.

    ``json.dumps`` defaults give ``", "`` / ``": "`` separators; the glue
    strings below match them so the output is one consistent document.
    """
    yield "{"
    yield '"event": ' + json.dumps(export["event"]) + ", "
    for i, key in enumerate(("tracks", "judges", "teams", "projects", "scores")):
        if i:
            yield ", "
        yield f'"{key}": ['
        for j, row in enumerate(export[key]):
            if j:
                yield ", "
            yield json.dumps(row)
        yield "]"
    yield "}"
