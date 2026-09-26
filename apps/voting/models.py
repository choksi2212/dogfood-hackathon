"""Voting models for T3 (Community Voting).

Three tables:

* ``Vote``        — one row per (event, project, voter_key). A re-cast of
  the same ballot updates ``votes`` rather than creating a new row.
* ``VoteBudget``  — quadratic-mode only; tracks how many "credits" a
  voter has spent in this event.
* ``VoteAudit``   — append-only log of every cast / retract. The
  ``Vote`` row is mutated; the audit row is preserved.

The ``voter_key`` field is how we identify a voter without a hard login:

* authenticated   -> ``user:<uuid>``
* anonymous       -> ``fp:<sha256(ip + user_agent)[:32]>``

This gives us simple / quadratic voting, retraction, and a tamper-evident
audit trail. Anti-abuse (fingerprint collisions, rate limits) is handled
upstream by the proxy and the ``abuse`` app.
"""
import uuid

from django.db import models


class Vote(models.Model):
    """A ballot for one (event, project) from one voter.

    ``votes`` is the integer the voter chose. In ``simple`` mode this is
    always 1. In ``quadratic`` mode the voter pays ``votes**2`` credits
    out of their 100-credit budget for the event.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="votes"
    )
    project = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="votes",
    )
    voter_key = models.CharField(max_length=64)
    voter_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="votes",
    )
    voter_email_hash = models.CharField(max_length=64, blank=True)
    votes = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    retracted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "voting_vote"
        unique_together = ("event", "project", "voter_key")
        indexes = [
            models.Index(fields=["event", "voter_key"]),
            models.Index(fields=["event", "project"]),
        ]

    def __str__(self) -> str:
        return f"{self.event.slug}/{self.project_id}/{self.voter_key}:{self.votes}"

    @property
    def is_retracted(self) -> bool:
        return self.retracted_at is not None

    @property
    def effective_votes(self) -> int:
        """Number of votes that count toward the running tally.

        A retracted ballot contributes zero. Otherwise it contributes
        ``self.votes``. Use this for any aggregation — never sum
        ``votes`` directly.
        """
        if self.retracted_at is not None:
            return 0
        return self.votes


class VoteBudget(models.Model):
    """Quadratic-mode per-voter credit balance.

    Created lazily on first cast. Each n-vote ballot costs n^2 credits;
    retraction refunds n^2 credits. The cap is 100 — see
    ``VoteView.post`` for the check.
    """

    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="vote_budgets"
    )
    voter_key = models.CharField(max_length=64)
    spent_credits = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voting_votebudget"
        unique_together = ("event", "voter_key")

    def __str__(self) -> str:
        return f"{self.event.slug}/{self.voter_key}:{self.spent_credits}"


class VoteAudit(models.Model):
    """Append-only audit trail for ``cast`` and ``retract`` actions.

    Every successful state change in ``VoteView`` produces one row here.
    The ``vote`` FK is preserved on retract via the original row's id —
    we never delete ballots, so the audit link stays valid.
    """

    ACTION_CHOICES = [
        ("cast", "Cast"),
        ("retract", "Retract"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vote = models.ForeignKey(
        Vote, on_delete=models.CASCADE, related_name="audit_entries"
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "voting_voteaudit"
        indexes = [
            models.Index(fields=["vote", "action"]),
            models.Index(fields=["at"]),
        ]
        ordering = ["-at"]

    def __str__(self) -> str:
        return f"{self.action} {self.vote_id} @ {self.at:%Y-%m-%d %H:%M}"
