"""
No models here. The login account itself lives on core.Employee (see
config/settings.py: AUTH_USER_MODEL = "core.Employee") — there is
deliberately no separate accounts.User table. This app holds the
auth-flow views/serializers/permissions (login, password reset, the
role-based permission matrix) that operate on `get_user_model()`.
"""
