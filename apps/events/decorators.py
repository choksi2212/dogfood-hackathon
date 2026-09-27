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
