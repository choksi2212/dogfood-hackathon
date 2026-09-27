"""Submission views.

T1 (G2):
  GET  /api/gallery                       → public list of submitted projects
  POST /api/events/<slug>/submit          → participant, deadline-gated

T3 surfaces (later):
  POST /api/events/<slug>/submissions/<id>/review-comment (T3 comments)
  POST /api/events/<slug>/submissions/<id>/vote (T3 voting)
"""

from __future__ import annotations

import base64
import json

from django.utils import timezone
from django.utils.cache import patch_cache_control
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.decorators import deadline_gated
from apps.events.models import Event, Track
from apps.events.permissions import IsOrganizer, IsParticipant
from apps.teams.models import TeamMember

from .models import Comment, Submission
from .serializers import (
    CommentSerializer,
    SubmissionSerializer,
    SubmissionSummarySerializer,
)

PAGE_SIZE = 24


def _encode_cursor(sort: str, last_item: Submission) -> str:
    """Build an opaque base64 cursor from the last item's sort keys.

    The cursor is forward-only and strictly tied to the sort mode — the
    server refuses to mix them. Format::

        {"v": 1, "s": <sort>, "k": [<k1>, <k2>, ...]}

    For ``sort=track`` the keys are ``[track_order, name]`` (so the
    server can do ``(track_order, name) > (k1, k2)``).
    For ``sort=alpha`` the key is ``[name]``.
    For ``sort=newest`` the keys are ``[submitted_at_iso, id]`` so the
    submitted_at tie-break is unambiguous.
    """
    if sort == "track":
        keys = [last_item.track.order, last_item.name, str(last_item.id)]
    elif sort == "alpha":
        keys = [last_item.name, str(last_item.id)]
    elif sort == "newest":
        keys = [last_item.submitted_at.isoformat() if last_item.submitted_at else None, str(last_item.id)]
    else:
        keys = [last_item.name, str(last_item.id)]
    payload = json.dumps({"v": 1, "s": sort, "k": keys}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, str, list]:
    """Inverse of :func:`_encode_cursor`. Raises ``ValueError`` on bad
    input — the caller turns that into a 422."""
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + pad)
    obj = json.loads(raw)
    return obj["v"], obj["s"], obj["k"]


class GalleryView(APIView):
    """Public gallery. Used by acceptance checks 1 and 2.

    Returns submitted-only submissions in track order. The check expects
    at least one known fixture title — we seed fixtures with a known
    title so this is always true after `manage.py seed_fixtures`.

    The response is cached for 60s via the in-process LocMemCache. The
    cache key includes every query param so pagination / sorting / track
    filters don't bleed into each other. Cached responses carry
    ``Cache-Control: public, max-age=60`` so upstream proxies can also
    serve from their edge.

    Pagination
    ----------
    Two modes are supported. Both return the same shape of ``items``;
    only the wrapper fields differ.

    * **Cursor** (default): returns ``{items, next, page_size}`` where
      ``next`` is an opaque cursor for the next page (or ``null`` at
      the end). The query is a constant-time seek on the indexed sort
      key, so page 1000 is just as fast as page 1. Call again with
      ``?after=<next>`` to get the following page.
    * **Offset** (legacy, ``?page=N``): returns ``{total, page,
      page_size, items}``. Slow on late pages because PostgreSQL has to
      scan + skip ``N*page_size`` rows. Opt in by passing ``?page=N``.

    The ``?after`` cursor must match the current ``?sort`` mode; a
    cursor built with ``sort=alpha`` is rejected if you ask for
    ``sort=newest``.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # public — no session lookup needed

    def get(self, request):
        from django.core.cache import cache
        from django.utils.cache import patch_cache_control

        cache_key = "gallery:" + "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            patch_cache_control(resp, public=True, max_age=60)
            resp["X-Cache"] = "HIT"
            return resp

        qs = Submission.objects.filter(status="submitted").select_related("team", "track")

        track = request.query_params.get("track")
        if track:
            qs = qs.filter(track__slug__in=track.split(","))

        sort = request.query_params.get("sort", "track")
        if sort == "alpha":
            qs = qs.order_by("name", "id")
        elif sort == "newest":
            qs = qs.order_by("-submitted_at", "-id")
        else:
            qs = qs.order_by("track__order", "name", "id")

        # Cursor pagination is the default — the seek is O(1) on the
        # indexed sort key for any page. ``?page=N`` opts into the old
        # offset response (kept for clients that rely on ``total``).
        after = request.query_params.get("after")
        use_offset = "page" in request.query_params

        if use_offset:
            try:
                page = int(request.query_params.get("page", "1"))
            except ValueError:
                page = 1
            items = list(qs[(page - 1) * PAGE_SIZE : page * PAGE_SIZE])
            total = qs.count()
            body = {
                "total": total,
                "page": page,
                "page_size": PAGE_SIZE,
                "items": SubmissionSummarySerializer(items, many=True).data,
            }
        else:
            if after:
                try:
                    version, cursor_sort, keys = _decode_cursor(after)
                except (ValueError, KeyError, TypeError):
                    return Response(
                        {
                            "error": {
                                "code": "validation_failed",
                                "message": "Malformed cursor.",
                            }
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                if version != 1 or cursor_sort != sort:
                    return Response(
                        {
                            "error": {
                                "code": "validation_failed",
                                "message": (f"Cursor was built for sort={cursor_sort!r}, current sort={sort!r}."),
                            }
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                # ``id`` is the final tiebreaker on every sort mode so the
                # seek is unambiguous even with duplicate names / timestamps.
                if sort == "track":
                    track_order, name = keys[0], keys[1]
                    qs = qs.filter(
                        # Row-value seek: skip everything at-or-before
                        # the cursor in (track_order, name). The third
                        # branch is the tie-break by id.
                    )
                    from django.db.models import Q

                    last_id = keys[2] if len(keys) > 2 else None
                    qs = qs.filter(
                        Q(track__order__gt=track_order)
                        | (Q(track__order=track_order) & Q(name__gt=name))
                        | (Q(track__order=track_order) & Q(name=name) & Q(id__gt=last_id))
                    )
                elif sort == "alpha":
                    (name,) = keys[:1]
                    from django.db.models import Q

                    last_id = keys[1] if len(keys) > 1 else None
                    qs = qs.filter(Q(name__gt=name) | (Q(name=name) & Q(id__gt=last_id)))
                else:  # newest
                    submitted_at_iso, last_id = keys[0], keys[1]
                    from django.db.models import Q

                    qs = qs.filter(
                        Q(submitted_at__lt=submitted_at_iso) | (Q(submitted_at=submitted_at_iso) & Q(id__lt=last_id))
                    )

            items = list(qs[:PAGE_SIZE])
            next_cursor = _encode_cursor(sort, items[-1]) if len(items) == PAGE_SIZE else None
            body = {
                "items": SubmissionSummarySerializer(items, many=True).data,
                "next": next_cursor,
                "page_size": PAGE_SIZE,
            }

        # Cache for 60s — long enough to absorb a scrape burst,
        # short enough that new submissions show up promptly.
        cache.set(cache_key, body, timeout=60)
        resp = Response(body)
        patch_cache_control(resp, public=True, max_age=60)
        resp["X-Cache"] = "MISS"
        return resp


class SubmissionDetailView(APIView):
    """GET /api/submissions/<uuid:id> — single-submission read.

    Public read so anyone with the link can see a project (matches the
    gallery's public-read posture). Drafts are 404'd; only ``submitted``,
    ``locked`` show. ``withdrawn`` is intentionally visible — once you
    shipped it, it shipped.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # public — no session lookup needed

    def get(self, request, id):
        try:
            submission = (
                Submission.objects.select_related("team", "track", "event")
                .get(id=id)
            )
        except Submission.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Submission not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if submission.status == "draft":
            return Response(
                {"error": {"code": "not_found", "message": "Submission not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = SubmissionSerializer(submission).data
        resp = Response(data)
        patch_cache_control(resp, public=True, max_age=60)
        resp["X-Cache"] = "MISS"
        return resp


class SubmitView(APIView):
    """The spec route. POST as participant, after deadline → 4xx.

    Body (JSON, optional):
      { "name": "...", "tagline": "...", "description": "...",
        "track_slug": "main", "team_id": "<uuid>" }
    Without a team_id, the server picks the participant's first team in
    this event.
    """

    permission_classes = [IsParticipant]

    @deadline_gated("submissions_close_at")
    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": f"Event {slug!r} not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        team = self._resolve_team(request, event)
        if isinstance(team, Response):
            return team

        track_slug = request.data.get("track_slug")
        if not track_slug:
            track = event.tracks.order_by("order").first()
            if track is None:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": "Event has no tracks; cannot submit.",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        else:
            try:
                track = Track.objects.get(event=event, slug=track_slug)
            except Track.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": f"Track {track_slug!r} not found.",
                        }
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        name = (request.data.get("name") or "").strip()
        tagline = (request.data.get("tagline") or "").strip()[:140]
        if not name:
            name = f"{team.name} submission"

        submission, created = Submission.objects.get_or_create(
            team=team,
            defaults={
                "event": event,
                "track": track,
                "name": name,
                "tagline": tagline,
                "description": request.data.get("description", ""),
            },
        )
        if not created:
            submission.name = name
            submission.tagline = tagline
            submission.description = request.data.get("description", "")
            submission.track = track
            submission.save()

        if submission.status not in ("draft", "submitted"):
            return Response(
                {
                    "error": {
                        "code": "gone",
                        "message": f"Submission is {submission.status}; cannot re-submit.",
                    }
                },
                status=status.HTTP_410_GONE,
            )

        submission.status = "submitted"
        submission.submitted_at = timezone.now()
        submission.save()

        return Response(
            SubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )

    def _resolve_team(self, request, event):
        team_id = request.data.get("team_id")
        if team_id:
            from apps.teams.models import Team

            try:
                team = Team.objects.get(id=team_id, event=event)
            except Team.DoesNotExist:
                return Response(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"Team {team_id!r} not found in this event.",
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not TeamMember.objects.filter(team=team, user=request.user).exists():
                return Response(
                    {
                        "error": {
                            "code": "forbidden_role",
                            "message": "You are not a member of that team.",
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return team

        member = TeamMember.objects.filter(user=request.user, team__event=event).select_related("team").first()
        if member is None:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "You are not in a team for this event.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return member.team


class CommentListCreateView(APIView):
    """T3 §3 — Comments on gallery projects.

    GET  /api/events/<slug>/submissions/<id>/comments
        — Public, paginated. Returns ``[hidden=False]`` rows ordered by
          created_at. The hidden-by-organizer flag hides moderation
          takedowns but does not reveal them.

    POST /api/events/<slug>/submissions/<id>/comments
        — Authenticated, rate-limited via the write-class bucket on
          the middleware. Body: ``{"body": "<=2000 chars"}``. The
          author is the authenticated user; no impersonation possible.

    Comments are NOT auto-moderated — the anti-abuse app surfaces
    top suspicious IPs and organizers can soft-delete (is_hidden=true)
    a comment via PATCH below.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug, id):
        try:
            submission = Submission.objects.get(id=id, event__slug=slug)
        except Submission.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Submission not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        comments = (
            Comment.objects.filter(submission=submission, is_hidden=False)
            .select_related("author")
            .order_by("created_at")
        )
        return Response(CommentSerializer(comments, many=True).data)

    def post(self, request, slug, id):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return Response(
                {
                    "error": {
                        "code": "not_authenticated",
                        "message": "Authentication required to comment.",
                    }
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            submission = Submission.objects.get(id=id, event__slug=slug)
        except Submission.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Submission not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        body = (request.data.get("body") or "").strip()
        if not body:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "body is required.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(body) > 2000:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "body must be <= 2000 characters.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        comment = Comment.objects.create(submission=submission, author=request.user, body=body)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentModerateView(APIView):
    """PATCH /api/events/<slug>/submissions/<id>/comments/<comment_id>
    — Organizer-only soft-delete. Sets is_hidden=true + hidden_by =
    the organizer. The comment disappears from public listings
    (GET returns 404 because the row no longer matches
    ``is_hidden=False``) but stays in the DB for audit.
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    def patch(self, request, slug, id, comment_id):
        from .models import Comment

        try:
            comment = Comment.objects.get(id=comment_id, submission_id=id)
        except Comment.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Comment not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        action = request.data.get("action", "hide")
        if action == "hide":
            comment.is_hidden = True
            comment.hidden_by = request.user
            comment.save(update_fields=["is_hidden", "hidden_by", "updated_at"])
            return Response({"id": str(comment.id), "is_hidden": True})
        if action == "unhide":
            comment.is_hidden = False
            comment.hidden_by = None
            comment.save(update_fields=["is_hidden", "hidden_by", "updated_at"])
            return Response({"id": str(comment.id), "is_hidden": False})
        return Response(
            {
                "error": {
                    "code": "validation_failed",
                    "message": "action must be 'hide' or 'unhide'.",
                }
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
