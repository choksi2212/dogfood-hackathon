"""DRF exception handler. Wraps every error in a consistent envelope so the
judge-console and the run.py checker can match against known shapes.

Envelope:
  { "error": { "code": "...", "message": "...", "detail": {...} } }
"""

from rest_framework.views import exception_handler

_CODE_BY_STATUS = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    422: "validation_failed",
    429: "rate_limited",
    500: "server_error",
    503: "service_unavailable",
}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    code = _CODE_BY_STATUS.get(response.status_code, "error")
    detail = response.data if isinstance(response.data, dict) else {"raw": response.data}

    # If the view already wrapped it, respect that.
    if isinstance(detail, dict) and "error" in detail and isinstance(detail["error"], dict):
        return response

    message = (
        detail.get("detail")
        if isinstance(detail, dict) and "detail" in detail and isinstance(detail["detail"], str)
        else None
    ) or _default_message(response.status_code)

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "detail": detail if detail != {"detail": message} else {},
        }
    }
    return response


def _default_message(status_code: int) -> str:
    return {
        400: "Bad request.",
        401: "Authentication required.",
        403: "Forbidden.",
        404: "Not found.",
        405: "Method not allowed.",
        409: "Conflict.",
        410: "Gone.",
        422: "Validation failed.",
        429: "Too many requests.",
        500: "Internal server error.",
        503: "Service unavailable.",
    }.get(status_code, "Error.")
