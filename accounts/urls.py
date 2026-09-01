from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    LoginView,
    UserViewSet,
    me,
    password_reset_confirm,
    password_reset_request,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("me/", me, name="me"),
    path("password-reset/", password_reset_request, name="password_reset"),
    path("password-reset-confirm/", password_reset_confirm, name="password_reset_confirm"),
    path("", include(router.urls)),
]
