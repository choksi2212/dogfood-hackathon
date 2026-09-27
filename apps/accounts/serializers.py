from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active", "memberships"]
        read_only_fields = ["id", "is_active"]

    def get_memberships(self, obj):
        return [{"event": m.event.slug, "role": m.role} for m in obj.memberships.select_related("event")]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        # AbstractUser requires a non-empty unique username; use the
        # email as the username so login-by-email continues to work.
        # Same fix as seed_fixtures._ensure_user and
        # apps.judging.views.BatchInviteView.post.
        user = User(username=validated_data.get("email"), **validated_data)
        if password:
            validate_password(password)
            user.set_password(password)
        user.save()
        return user
