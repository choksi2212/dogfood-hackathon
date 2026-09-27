"""Quota helpers — enforce Plan limits at event-creation time.

The enforcement model:

  * Every Plan has ``max_events`` (organizer-wide), and per-event
    caps (``max_judges_per_event``, ``max_submissions_per_event``).
    A value of ``None`` means "unlimited".

  * ``check_event_quota(organizer)`` runs before the view that
    creates a new Event. If the organizer is already running
    ``max_events`` (across all paid plans), the call fails with
    ``quota_exceeded``.

  * ``check_submission_quota(event)`` and
    ``check_judge_quota(event)`` are the per-event caps. They run
    inside the relevant create-view paths.

Quotas are enforced at the request boundary, not via DB constraints.
This is intentional: a denied event creation is a clear 422, not a
postgres ``unique_violation`` exception.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuotaResult:
    ok: bool
    reason: str = ""
    limit: int | None = None
    current: int = 0


def _check_cap(current: int, limit: int | None) -> QuotaResult:
    if limit is None:
        return QuotaResult(ok=True)
    if current >= limit:
        return QuotaResult(
            ok=False,
            reason=f"Quota exceeded ({current}/{limit}).",
            limit=limit,
            current=current,
        )
    return QuotaResult(ok=True)


def check_event_quota(organizer) -> QuotaResult:
    """Can ``organizer`` create one more Event under their current plan?

    The "current plan" is the lowest-quota plan across all the
    organizer's active BillingAccounts — i.e., the most restrictive.
    In practice every organizer has one plan; this is defensive.

    For an organizer with no BillingAccount yet, the limit is the
    free plan's limit (a fresh signup gets the free tier by default;
    creating the first event consumes that one slot).
    """
    from .models import BillingAccount, Plan

    accounts = BillingAccount.objects.filter(
        event__created_by=organizer,
        status__in=("trial", "active"),
    ).select_related("plan")

    if not accounts.exists():
        # No billing account yet — the first event they create will
        # get the free plan attached; report against that limit.
        try:
            default_limit = Plan.objects.get(name="free").max_events
        except Plan.DoesNotExist:
            default_limit = None
        return QuotaResult(ok=True, limit=default_limit, current=0)

    most_restrictive_limit: int | None = None
    for account in accounts:
        plan_limit = account.plan.max_events
        if most_restrictive_limit is None:
            most_restrictive_limit = plan_limit
        elif plan_limit is not None and (
            most_restrictive_limit is None or plan_limit < most_restrictive_limit
        ):
            most_restrictive_limit = plan_limit

    return _check_cap(accounts.count(), most_restrictive_limit)


def check_submission_quota(event) -> QuotaResult:
    """Can ``event`` accept one more submission under its plan?"""
    from apps.submissions.models import Submission

    limit = _limit_for(event)
    current = Submission.objects.filter(event=event).count()
    return _check_cap(current, limit)


def check_judge_quota(event) -> QuotaResult:
    """Can ``event`` accept one more judge membership under its plan?"""
    from apps.events.models import Membership

    limit = _limit_for(event, attr="max_judges_per_event")
    current = Membership.objects.filter(event=event, role="judge").count()
    return _check_cap(current, limit)


def _limit_for(event, *, attr: str = "max_submissions_per_event"):
    account = getattr(event, "billing", None)
    if account is None or account.plan is None:
        return None  # No billing → unlimited (free tier default)
    return getattr(account.plan, attr)


# --- Coordinator-facing defaults --------------------------------------------

DEFAULT_FREE_PLAN = {
    "name": "free",
    "display_name": "Free (Trial)",
    "monthly_price_cents": 0,
    "max_events": 1,
    "max_judges_per_event": 5,
    "max_submissions_per_event": 50,
}

DEFAULT_PRO_PLAN = {
    "name": "pro",
    "display_name": "Pro",
    "monthly_price_cents": 9900,
    "max_events": 25,
    "max_judges_per_event": 50,
    "max_submissions_per_event": 500,
}

DEFAULT_ENTERPRISE_PLAN = {
    "name": "enterprise",
    "display_name": "Enterprise",
    "monthly_price_cents": 99000,
    "max_events": None,           # unlimited
    "max_judges_per_event": None,
    "max_submissions_per_event": None,
}


def seed_default_plans() -> list:
    """Idempotently upsert the three default plans. Returns the list
    of ``Plan`` instances."""
    from .models import Plan

    created: list = []
    for defaults in (
        DEFAULT_FREE_PLAN,
        DEFAULT_PRO_PLAN,
        DEFAULT_ENTERPRISE_PLAN,
    ):
        plan, _ = Plan.objects.update_or_create(
            name=defaults["name"],
            defaults={
                "display_name": defaults["display_name"],
                "monthly_price_cents": defaults["monthly_price_cents"],
                "max_events": defaults["max_events"],
                "max_judges_per_event": defaults["max_judges_per_event"],
                "max_submissions_per_event": defaults["max_submissions_per_event"],
            },
        )
        created.append(plan)
    return created


def default_free_plan():
    from .models import Plan

    return Plan.objects.get(name="free")
