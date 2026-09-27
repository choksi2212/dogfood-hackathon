from rest_framework.permissions import BasePermission

from .models import Event, Membership


def _get_event(view):
    """Resolve the event from URL kwargs (slug → Event)."""
    slug = view.kwargs.get("slug")
    if slug:
        try:
            return Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            return None
    return None


def _has_role(request, event, role):
    if not request.user or not request.user.is_authenticated:
        return False
    if getattr(request.user, "is_admin_role", False):
        return True
    return Membership.objects.filter(user=request.user, event=event, role=role).exists()


class IsInEvent(BasePermission):
    """The user has any membership in the event."""

    def has_permission(self, request, view):
        event = _get_event(view)
        if not event:
            return False
        if getattr(request.user, "is_admin_role", False):
            return True
        return Membership.objects.filter(user=request.user, event=event).exists()


class IsParticipant(IsInEvent):
    message = "Only participants of this event can do that."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        event = _get_event(view)
        return _has_role(request, event, "participant")


class IsJudge(IsInEvent):
    message = "Only judges of this event can do that."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        event = _get_event(view)
        return _has_role(request, event, "judge")


class IsOrganizer(IsInEvent):
    message = "Only organizers of this event can do that."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        event = _get_event(view)
        return _has_role(request, event, "organizer")
