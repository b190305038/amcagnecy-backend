from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import RoleModulePermission
from .serializers import LoginSerializer, MeSerializer, UserSerializer

User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    """Start a password reset: email the user a tokenised reset link.

    Always returns a generic 200 so the endpoint can't be used to probe which
    emails have accounts. In DEBUG the link is also returned in the response
    body so the flow is testable without a live mail server.
    """
    email = str((request.data or {}).get("email", "")).strip()
    resp = {"detail": "If that email is registered, a reset link has been sent."}
    if email:
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            try:
                send_mail(
                    subject="Reset your A.M.C. Agency password",
                    message=(
                        f"Hello {user.name or user.email},\n\n"
                        f"Use the link below to set a new password. It expires shortly.\n\n"
                        f"{reset_url}\n\n"
                        f"If you didn't request this, you can ignore this email."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            if settings.DEBUG:
                resp["debug_reset_url"] = reset_url
    return Response(resp)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """Complete a password reset given a valid uid + token."""
    data = request.data or {}
    uid = str(data.get("uid", ""))
    token = str(data.get("token", ""))
    new_password = str(data.get("new_password", ""))

    if len(new_password) < 4:
        return Response(
            {"detail": "Password must be at least 4 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {"detail": "This reset link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"detail": "Password updated. You can now sign in."})


class LoginView(TokenObtainPairView):
    """POST email + password -> { access, refresh, user }."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the currently authenticated user's profile + permission map."""
    return Response(MeSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """CRUD for the Users management page. `module='users'` -> superuser-only writes."""

    queryset = User.objects.all().order_by("name")
    serializer_class = UserSerializer
    permission_classes = [RoleModulePermission]
    module = "users"
    search_fields = ["name", "email", "role", "branch"]
    filterset_fields = ["role", "branch", "status"]
    ordering_fields = ["name", "email", "role"]

    @action(detail=True, methods=["post"])
    def set_password(self, request, pk=None):
        """Reset a user's password. Gated to the 'users' module (Manager
        only) by RoleModulePermission, so no other role can reach it."""
        user = self.get_object()
        password = (request.data or {}).get("password", "")
        if not password or len(str(password)) < 4:
            return Response(
                {"detail": "Password must be at least 4 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(str(password))
        user.save(update_fields=["password"])
        return Response({"detail": f"Password reset for {user.email}."})
