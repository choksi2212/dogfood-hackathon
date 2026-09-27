"""Billing models for multi-tenant event hosting.

Three tables back the company's billing story:

* ``Plan``               — a priced tier (free / pro / enterprise) with
                            per-tier quotas.
* ``BillingAccount``     — one row per Event linking the event to its
                            current plan + billing cycle. Source of
                            truth for "is this event within quota?"
* ``Invoice``            — append-only log of every charge / refund /
                            plan-change. The audit-trail sister of
                            the mutable BillingAccount row.

The company is paid per active Event, not per User. The model is
deliberately flat — no Customer / Subscription / PaymentMethod
hierarchy. A real Stripe integration would slot in here; for the
hackathon demo the upgrade flow is a coordinator-only endpoint that
mutates ``BillingAccount.plan`` and writes an ``Invoice`` row.
"""
import uuid

from django.db import models


class Plan(models.Model):
    """A priced tier. Quotas are enforced at event-creation time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=40, unique=True)
    display_name = models.CharField(max_length=80)
    monthly_price_cents = models.IntegerField(default=0)

    # Quotas. ``None`` means "unlimited".
    max_events = models.IntegerField(null=True, blank=True)
    max_judges_per_event = models.IntegerField(null=True, blank=True)
    max_submissions_per_event = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "billing_plan"
        ordering = ["monthly_price_cents"]

    def __str__(self) -> str:
        return f"{self.name} (${self.monthly_price_cents / 100:.2f}/mo)"

    @property
    def is_free(self) -> bool:
        return self.monthly_price_cents == 0


class BillingAccount(models.Model):
    """One row per Event, holding the current plan + cycle dates."""

    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(
        "events.Event", on_delete=models.CASCADE, related_name="billing"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="accounts"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="trial")
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_billingaccount"
        indexes = [models.Index(fields=["plan", "status"])]

    def __str__(self) -> str:
        return f"{self.event.slug} → {self.plan.name} ({self.status})"


class Invoice(models.Model):
    """Append-only log of charges / refunds / plan changes."""

    KIND_CHOICES = [
        ("charge", "Charge"),
        ("refund", "Refund"),
        ("plan_change", "Plan Change"),
        ("adjustment", "Adjustment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="invoices"
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    amount_cents = models.IntegerField()
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices_created",
    )

    class Meta:
        db_table = "billing_invoice"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["account", "created_at"])]

    def __str__(self) -> str:
        sign = "-" if self.kind in ("refund", "adjustment") else ""
        return f"{self.kind} {sign}${abs(self.amount_cents) / 100:.2f}"
