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
    WebSocketAuth,
    get_authenticated_user,
    get_current_staff_user,
    get_current_user,
    get_django_request,
    require_websocket_user,
    resolve_websocket_auth,
    session_auth_resolver,
    validate_websocket_origin,
)
from django_fastapi.csrf import csrf_exempt, require_csrf
from django_fastapi.database import (
    aclose_db_connections,
    database_sync_to_async,
    django_db,
)
from django_fastapi.fastapi import (
    create_fastapi_app,
    create_websocket_app,
    get_fastapi_prefix,
)
from django_fastapi.responses import django_response_to_fastapi

__version__ = version("django-fastapi")

__all__ = [
    "__version__",
    "AuthResolver",
    "AuthResolverResult",
    "AuthUser",
    "WebSocketAuth",
    "aclose_db_connections",
    "database_sync_to_async",
    "django_db",
    "create_fastapi_app",
    "create_websocket_app",
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
    "require_websocket_user",
    "resolve_websocket_auth",
    "session_auth_resolver",
    "validate_websocket_origin",
]
