from rest_framework import serializers

from .models import Comment, Submission


class SubmissionSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    track_slug = serializers.SlugField(source="track.slug", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "team",
            "team_name",
            "event",
            "track",
            "track_slug",
            "name",
            "tagline",
            "description",
            "thumbnail_path",
            "demo_video_url",
            "repo_url",
            "live_url",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        ]


class SubmissionSummarySerializer(serializers.ModelSerializer):
    """Lean shape for the public gallery — keeps payload small."""

    track_slug = serializers.SlugField(source="track.slug", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "name",
            "tagline",
            "description",
            "track_slug",
            "thumbnail_path",
            "submitted_at",
        ]


class CommentSerializer(serializers.ModelSerializer):
    """T3 §3 — comment shape.

    Author info is a strict allow-list — we serialize
    ``author.email_hash`` (sha256-truncated) so the gallery can
    show a stable avatar without leaking PII. The full email is
    never serialized.
    """

    author_email_hash = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "submission",
            "author",
            "author_email_hash",
            "body",
            "created_at",
            "is_hidden",
        ]
        read_only_fields = [
            "id",
            "submission",
            "author",
            "author_email_hash",
            "created_at",
            "is_hidden",
        ]

    def get_author_email_hash(self, obj):
        import hashlib

        if obj.author is None:
            return None
        return hashlib.sha256(obj.author.email.encode()).hexdigest()[:16]
