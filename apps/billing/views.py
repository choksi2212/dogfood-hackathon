"""Billing views — list plans + upgrade / downgrade.

Routes (under /api/billing/):

  GET  /api/billing/plans                 list the available plans
  GET  /api/billing/account/<slug>        current account state for an event
  POST /api/billing/account/<slug>/upgrade organizer-only, swap plan
                                          + write an Invoice row
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.models import Event
from apps.events.permissions import IsOrganizer

from .models import BillingAccount, Invoice, Plan
from .quotas import seed_default_plans


class PlanListView(APIView):
    """GET /api/billing/plans — public listing of all active plans."""

    permission_classes = []

    def get(self, _request):
        plans = Plan.objects.filter(is_active=True).order_by("monthly_price_cents")
        return Response(
            [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "display_name": p.display_name,
                    "monthly_price_cents": p.monthly_price_cents,
                    "max_events": p.max_events,
                    "max_judges_per_event": p.max_judges_per_event,
                    "max_submissions_per_event": p.max_submissions_per_event,
                    "is_free": p.is_free,
                }
                for p in plans
            ]
        )


class BillingAccountView(APIView):
    """GET /api/billing/account/<slug> — current account state."""

    permission_classes = [IsAuthenticated, IsOrganizer]

    def get(self, request, slug):
        event = Event.objects.get(slug=slug)
        account = _ensure_account(event)
        return Response(
            {
                "event": event.slug,
                "plan": account.plan.name,
                "status": account.status,
                "current_period_start": (
                    account.current_period_start.isoformat()
                    if account.current_period_start else None
                ),
                "current_period_end": (
                    account.current_period_end.isoformat()
                    if account.current_period_end else None
                ),
            }
        )


class UpgradePlanView(APIView):
    """POST /api/billing/account/<slug>/upgrade — swap to a new plan.

    Body: ``{"plan_name": "pro"}``.
    Writes an Invoice row of kind ``plan_change`` so the audit trail
    shows the upgrade. Real Stripe integration would replace this
    with a checkout-session redirect; the surface is the same.
    """

    permission_classes = [IsAuthenticated, IsOrganizer]

    @transaction.atomic
    def post(self, request, slug):
        event = Event.objects.get(slug=slug)
        plan_name = (request.data.get("plan_name") or "").strip()
        if not plan_name:
            return Response(
                {"error": {"code": "validation_failed", "message": "plan_name required."}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        try:
            new_plan = Plan.objects.get(name=plan_name, is_active=True)
        except Plan.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": f"Unknown plan {plan_name!r}."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        account = _ensure_account(event)
        old_plan = account.plan

        # Don't double-write an upgrade-invoice for an idempotent call.
        if old_plan.id == new_plan.id:
            return Response(
                {
                    "event": event.slug,
                    "plan": new_plan.name,
                    "status": account.status,
                    "changed": False,
                }
            )

        now = timezone.now()
        account.plan = new_plan
        account.status = "active"
        account.current_period_start = now
        account.current_period_end = now + timezone.timedelta(days=30)
        account.save()

        Invoice.objects.create(
            account=account,
            kind="plan_change",
            amount_cents=new_plan.monthly_price_cents,
            description=f"Upgrade from {old_plan.name} to {new_plan.name}",
            created_by=request.user,
        )

        return Response(
            {
                "event": event.slug,
                "plan": new_plan.name,
                "status": account.status,
                "changed": True,
            }
        )


def _ensure_account(event: Event) -> BillingAccount:
    """Get-or-create the BillingAccount for an event, defaulting to
    the free plan. Idempotent."""
    from .quotas import default_free_plan

    try:
        return event.billing
    except BillingAccount.DoesNotExist:
        pass

    # Seed default plans lazily on first billing access. The seed is
    # idempotent so repeated calls are free.
    if not Plan.objects.exists():
        seed_default_plans()

    free = default_free_plan()
    now = timezone.now()
    return BillingAccount.objects.create(
        event=event,
        plan=free,
        status="trial",
        current_period_start=now,
        current_period_end=now + timezone.timedelta(days=14),
    )
