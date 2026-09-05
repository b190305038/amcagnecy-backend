from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    LoginView,
    me,
    password_reset_confirm,
    password_reset_request,
)

# User CRUD lives at /api/employees/ (core.Employee is the login account
# itself — see core/models.py). There is no /api/auth/users/ anymore.
urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", me, name="me"),
    path("password-reset/", password_reset_request, name="password_reset"),
    path("password-reset-confirm/", password_reset_confirm, name="password_reset_confirm"),
]
