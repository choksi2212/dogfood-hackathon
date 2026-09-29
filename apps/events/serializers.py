from rest_framework import serializers

from .models import Event, Membership, Prize, Rubric, RubricCriterion, Track


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = ["id", "name", "slug", "description", "order"]


class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prize
        fields = ["id", "name", "value", "track", "order"]


class RubricCriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricCriterion
        fields = ["id", "name", "description", "weight", "min", "max", "order"]


class RubricSerializer(serializers.ModelSerializer):
    criteria = RubricCriterionSerializer(many=True)

    class Meta:
        model = Rubric
        fields = ["id", "name", "criteria"]


class EventSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    prizes = PrizeSerializer(many=True, read_only=True)
    rubric = RubricSerializer(read_only=True)
    state = serializers.CharField(read_only=True)
    # Issues #47/#48: prizes and custom_questions had no write path —
    # the serializer dropped them on create/update. Prizes are replaced
    # wholesale when provided (same semantics as the rubric endpoint);
    # custom_questions is a plain JSONField on Event, persisted as-is.
    prizes_in = PrizeSerializer(many=True, write_only=True, required=False)
    custom_questions = serializers.JSONField(required=False)

    class Meta:
        model = Event
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "open_at",
            "submissions_close_at",
            "judging_open_at",
            "judging_close_at",
            "results_at",
            "voting_mode",
            "pairwise_enabled",
            "custom_questions",
            "tracks",
            "prizes",
            "prizes_in",
            "rubric",
            "state",
        ]
        read_only_fields = ["id", "tracks", "prizes", "rubric", "state"]

    def _apply_prizes(self, event, prizes_data):
        from .models import Prize, Track

        if prizes_data is None:
            return
        event.prizes.all().delete()
        for order, p in enumerate(prizes_data):
            track = None
            track_id = p.get("track")
            if track_id:
                track = Track.objects.filter(event=event, id=track_id).first() or Track.objects.filter(
                    event=event, slug=track_id
                ).first()
            Prize.objects.create(
                event=event,
                track=track,
                name=p.get("name", ""),
                value=p.get("value", 0) or 0,
                order=p.get("order", order),
            )

    def create(self, validated_data):
        prizes_data = validated_data.pop("prizes_in", None)
        custom_questions = validated_data.pop("custom_questions", None)
        if custom_questions is not None:
            validated_data["custom_questions"] = custom_questions
        event = super().create(validated_data)
        self._apply_prizes(event, prizes_data)
        return event

    def update(self, instance, validated_data):
        prizes_data = validated_data.pop("prizes_in", None)
        custom_questions = validated_data.pop("custom_questions", None)
        if custom_questions is not None:
            validated_data["custom_questions"] = custom_questions
        event = super().update(instance, validated_data)
        self._apply_prizes(event, prizes_data)
        return event


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "role",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
