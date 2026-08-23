from importlib.metadata import version

from django_fastapi.asgi import (
    get_django_fastapi_application,
    mount_django_fastapi_app,
    mount_fastapi_app,
)
from django_fastapi.auth import (
    AuthResolver,
    AuthResolverResult,
    AuthUser,
    get_authenticated_user,
    get_current_staff_user,
    get_current_user,
    get_django_request,
    session_auth_resolver,
)
from django_fastapi.csrf import csrf_exempt, require_csrf
from django_fastapi.fastapi import create_fastapi_app, get_fastapi_prefix
from django_fastapi.responses import django_response_to_fastapi

__version__ = version("django-fastapi")

__all__ = [
    "__version__",
    "AuthResolver",
    "AuthResolverResult",
    "AuthUser",
    "create_fastapi_app",
    "csrf_exempt",
    "django_response_to_fastapi",
    "get_authenticated_user",
    "get_current_staff_user",
    "get_current_user",
    "get_fastapi_prefix",
    "get_django_request",
    "get_django_fastapi_application",
    "mount_django_fastapi_app",
    "mount_fastapi_app",
    "require_csrf",
    "session_auth_resolver",
]
