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
            "tracks",
            "prizes",
            "rubric",
            "state",
        ]
        read_only_fields = ["id", "tracks", "prizes", "rubric", "state"]


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
