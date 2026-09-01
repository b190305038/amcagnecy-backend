from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .permissions import PERMS

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Matches the frontend `AppUser` shape: name, email, role, branch, status."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "id_number", "role", "branch", "status", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password", "") or "demo123"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    """The signed-in account plus a resolved permission map for the UI."""

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "id_number", "role", "branch", "status", "permissions"]

    def get_permissions(self, obj):
        return PERMS.get(obj.role, {"write": [], "delete": []})


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login by email/password. Embeds user profile claims in the token
    and returns the user object alongside the tokens."""

    username_field = User.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["name"] = user.name
        token["email"] = user.email
        token["role"] = user.role
        token["branch"] = user.branch
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = MeSerializer(self.user).data
        return data
