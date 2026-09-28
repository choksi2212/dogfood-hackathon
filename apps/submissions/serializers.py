from rest_framework import serializers

from .models import Comment, Submission, SubmissionAnswer, SubmissionImage


class SubmissionImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionImage
        fields = ["id", "url", "caption", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class SubmissionAnswerSerializer(serializers.ModelSerializer):
    """Per-submission answer to an event-defined custom question."""

    class Meta:
        model = SubmissionAnswer
        fields = ["id", "question_id", "value"]
        read_only_fields = ["id"]


class SubmissionSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    track_slug = serializers.SlugField(source="track.slug", read_only=True)
    # Nested write — accept `images: [{url, caption, order}]` and
    # `answers: [{question_id, value}]` in PUT/POST bodies. Images are
    # replaced wholesale (simple model — gallery rows are owned by the
    # submission). Answers upsert on (submission, question_id) so the
    # frontend can re-send the full list each save.
    images = SubmissionImageSerializer(many=True, required=False)
    answers = SubmissionAnswerSerializer(many=True, required=False)

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
            "tech_tags",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
            "images",
            "answers",
        ]
        read_only_fields = [
            "id",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        answers = validated_data.pop("answers", [])
        instance = super().create(validated_data)
        for img in images:
            SubmissionImage.objects.create(submission=instance, **img)
        for ans in answers:
            SubmissionAnswer.objects.update_or_create(
                submission=instance,
                question_id=ans["question_id"],
                defaults={"value": ans["value"]},
            )
        return instance

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
        answers = validated_data.pop("answers", None)
        instance = super().update(instance, validated_data)
        if images is not None:
            # Wholesale replace — the frontend always sends the full
            # ordered list, and "delete one + recreate" is the simplest
            # way to honor reorder operations.
            instance.images.all().delete()
            for img in images:
                SubmissionImage.objects.create(submission=instance, **img)
        if answers is not None:
            for ans in answers:
                SubmissionAnswer.objects.update_or_create(
                    submission=instance,
                    question_id=ans["question_id"],
                    defaults={"value": ans["value"]},
                )
        return instance


class SubmissionSummarySerializer(serializers.ModelSerializer):
    """Lean shape for the public gallery — keeps payload small.

    Image gallery and tech tags are part of the full submission
    record (SubmissionSerializer) but intentionally NOT in the
    public gallery summary — the gallery list view shouldn't carry
    nested image lists or unbounded tag arrays. The detail page
    reads SubmissionSerializer directly when it wants the full set.
    """

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
