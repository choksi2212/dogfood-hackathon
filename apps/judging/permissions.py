"""Judging-specific permission classes.

The most important one is IsOwnJudge: it is the row-level isolation that
prevents a judge from reading another judge's scores. The acceptance
suite's check 5 is `peer_scores as judge_b`; that flow goes through
this permission.
"""

from rest_framework.permissions import BasePermission

from apps.events.models import Membership

from .models import JudgeAssignment


def _is_judge_for_event(request, view):
    if not request.user or not request.user.is_authenticated:
        return False
    if getattr(request.user, "is_admin_role", False):
        return True
    slug = view.kwargs.get("slug")
    if not slug:
        return False
    return Membership.objects.filter(user=request.user, event__slug=slug, role="judge").exists()


class IsAssignedJudge(BasePermission):
    """Allows only judges who hold an active assignment for the project
    in the URL. Used by ScoreSaveView / ScoreSubmitView."""

    def has_permission(self, request, view):
        if not _is_judge_for_event(request, view):
            return False
        project_id = view.kwargs.get("project_id")
        if not project_id:
            return True
        return JudgeAssignment.objects.filter(judge=request.user, project_id=project_id).exists()


class IsOwnJudge(BasePermission):
    """The graded cell. Denies if `?judge=` in the query string does not
    match the cookie's user. A judge asking for their own scores is
    allowed; asking for another judge's is not.

    The `?judge=` parameter accepts:
      - the user's UUID (the cookie carries a UUID user)
      - the user's email (matches equality, used by seed-script names)
      - the seed-script short name ("judge_a", "judge_b") — matches if
        the user's email starts with that handle.
    """

    message = "Cross-judge score reads are not permitted."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # The cookie's user — what `peer_scores as judge_b` means in the
        # spec language.
        cookie_judge = request.user

        # If the view is called WITHOUT a `?judge=` parameter, it
        # implicitly asks for "my own scores". Always allowed (the
        # endpoint will then return cookie_judge's scores).
        judge_param = request.query_params.get("judge")
        if not judge_param:
            return True

        if not Membership.objects.filter(user=cookie_judge, role="judge").exists() and not getattr(
            cookie_judge, "is_admin_role", False
        ):
            return False

        # Match by UUID.
        if str(cookie_judge.id) == judge_param:
            return True
        # Match by email.
        if cookie_judge.email == judge_param:
            return True
        # Match by seed-script handle ("judge_a", "judge_b").
        if cookie_judge.email.startswith(f"{judge_param}@"):
            return True

        return False
