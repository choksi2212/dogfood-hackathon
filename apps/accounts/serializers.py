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
        user = User(**validated_data)
        if password:
            validate_password(password)
            user.set_password(password)
        user.save()
        return user
