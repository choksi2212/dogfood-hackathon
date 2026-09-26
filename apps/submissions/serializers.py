from rest_framework import serializers

from .models import Submission


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
