from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .permissions import PERMS

User = get_user_model()  # core.Employee — see accounts/models.py


class MeSerializer(serializers.ModelSerializer):
    """The signed-in account plus a resolved permission map for the UI.

    `id_number` mirrors `id_no` under the name the frontend already expects
    (it predates the Employee/User merge — kept so src/lib/auth.tsx and the
    "view as" picker don't need a rename).
    """

    id_number = serializers.CharField(source="id_no", read_only=True)
    role = serializers.ReadOnlyField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id_number", "name", "email", "role", "branch", "status", "permissions"]

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
