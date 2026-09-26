"""Deadline decorator. Returns 422 if `now > event.<field>`, otherwise
forwards to the wrapped view. Used by submit, judge-score, vote, and
pairwise-ballot endpoints.
"""
import json
from functools import wraps

from django.http import HttpResponse
from django.utils import timezone

from .models import Event


def deadline_gated(field_name: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(self_or_request, request, *args, **kwargs):
            # Support both (self, request, ...) class-method style and
            # plain (request, ...) function style.
            if hasattr(self_or_request, "META"):
                request = self_or_request
            event_slug = kwargs.get("slug")
            if event_slug:
                try:
                    event = Event.objects.get(slug=event_slug)
                except Event.DoesNotExist:
                    return HttpResponse(status=404)
            else:
                event = None

            if event is not None:
                deadline = getattr(event, field_name, None)
                if deadline and timezone.now() > deadline:
                    return HttpResponse(
                        status=422,
                        content=json.dumps(
                            {
                                "error": {
                                    "code": "deadline_passed",
                                    "message": f"The {field_name.replace('_', ' ')} window has closed.",
                                    "detail": {"deadline": field_name},
                                }
                            }
                        ),
                        content_type="application/json",
                    )

            return view_func(self_or_request, request, *args, **kwargs)

        return wrapped

    return decorator


def opens_after(field_name: str):
    """Inverse of `deadline_gated`: returns 422 if `now < event.<field>`,
    otherwise forwards to the wrapped view.

    `deadline_gated` closes access once a deadline passes (submit,
    score). Voting has the opposite shape — it *opens* once
    registration closes (`views.py`'s own docstring: "voting opens at
    submissions_close_at") — so gating it with `deadline_gated` blocked
    voting for the entire window it was meant to be open in."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(self_or_request, request, *args, **kwargs):
            if hasattr(self_or_request, "META"):
                request = self_or_request
            event_slug = kwargs.get("slug")
            if event_slug:
                try:
                    event = Event.objects.get(slug=event_slug)
                except Event.DoesNotExist:
                    return HttpResponse(status=404)
            else:
                event = None

            if event is not None:
                opens_at = getattr(event, field_name, None)
                if opens_at and timezone.now() < opens_at:
                    return HttpResponse(
                        status=422,
                        content=json.dumps(
                            {
                                "error": {
                                    "code": "not_yet_open",
                                    "message": f"The {field_name.replace('_', ' ')} window has not opened yet.",
                                    "detail": {"opens_at": field_name},
                                }
                            }
                        ),
                        content_type="application/json",
                    )

            return view_func(self_or_request, request, *args, **kwargs)

        return wrapped

    return decorator
