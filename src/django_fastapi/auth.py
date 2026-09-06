from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from inspect import iscoroutinefunction
from io import BytesIO
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpRequest, HttpResponse
from django.http.request import split_domain_port, validate_host
from django.http.response import HttpResponseBase
from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string
from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)

from django_fastapi.database import database_sync_to_async

SETTINGS_NAME = "DJANGO_FASTAPI"
DEFAULT_AUTH_RESOLVERS = ("django_fastapi.auth.session_auth_resolver",)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.contrib.auth.models import AnonymousUser

    AuthUser: TypeAlias = AbstractBaseUser | AnonymousUser | SimpleLazyObject[Any]
else:
    AuthUser: TypeAlias = Any
AuthResolverResult: TypeAlias = AuthUser | None
AuthResolver: TypeAlias = Callable[
    [Request, HttpRequest],
    AuthResolverResult | Awaitable[AuthResolverResult],
]


class WebSocketAuth:
    """Resolved Django session and user for a WebSocket handshake."""

    def __init__(self, request: HttpRequest, user: AuthUser) -> None:
        self.request = request
        self.user = user
        self.session = request.session

    @property
    def session_key(self) -> str | None:
        return self.session.session_key


def _empty_response(_request: HttpRequest) -> HttpResponseBase:
    return HttpResponse()


async def get_django_request(request: Request) -> HttpRequest:
    """Build and cache a Django-compatible request for a FastAPI request."""
    existing_request = getattr(request.state, "django_request", None)
    if existing_request is not None:
        return cast(HttpRequest, existing_request)

    django_request = ASGIRequest(request.scope, BytesIO(await request.body()))
    middleware_cls = getattr(
        request.app.state, "django_fastapi_session_middleware", None
    )
    if middleware_cls is None:
        middleware_cls = validate_session_middleware(_get_settings_config(request))
    session_middleware = middleware_cls(_empty_response)
    session_middleware.process_request(django_request)
    if hasattr(session_middleware, "aprocess_request"):
        await session_middleware.aprocess_request(django_request)
    request.state.django_session_middleware = session_middleware
    cast(Any, django_request).user = await _resolve_user(request, django_request)
    request.state.django_request = django_request
    return django_request


def get_current_user(
    request: Annotated[HttpRequest, Depends(get_django_request)],
) -> AuthUser:
    """Return the current Django user or AnonymousUser."""
    return cast(AuthUser, request.user)


def get_authenticated_user(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AuthUser:
    """Return the current Django user or raise 401 for anonymous callers."""
    if not _is_authenticated(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def get_current_staff_user(
    user: Annotated[AuthUser, Depends(get_authenticated_user)],
) -> AuthUser:
    """Return the current staff user or raise 403."""
    if not bool(getattr(user, "is_staff", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required.",
        )
    return user


def session_auth_resolver(
    _request: Request,
    django_request: HttpRequest,
) -> AuthResolverResult:
    """Resolve Django's normal session-authenticated user."""
    from django.contrib.auth.middleware import AuthenticationMiddleware

    AuthenticationMiddleware(_empty_response).process_request(django_request)
    return cast(AuthUser, django_request.user)


async def resolve_websocket_auth(websocket: WebSocket) -> WebSocketAuth:
    """Resolve Django's session authentication for a WebSocket handshake."""
    existing = getattr(websocket.state, "django_websocket_auth", None)
    if isinstance(existing, WebSocketAuth):
        return existing

    scope = dict(websocket.scope)
    scope["type"] = "http"
    websocket_scheme = scope.get("scheme")
    if websocket_scheme in {"ws", "wss"}:
        scope["scheme"] = "https" if websocket_scheme == "wss" else "http"
    scope.setdefault("method", "GET")
    scope.setdefault("query_string", b"")
    request = ASGIRequest(scope, BytesIO())

    def resolve() -> WebSocketAuth:
        SessionMiddleware(_empty_response).process_request(request)
        user = session_auth_resolver(cast(Request, websocket), request)
        # AuthenticationMiddleware uses SimpleLazyObject; force it while still
        # inside Django's thread-sensitive sync boundary.
        bool(getattr(user, "is_authenticated", False))
        cast(Any, request).user = user
        return WebSocketAuth(request, cast(AuthUser, user))

    auth = await database_sync_to_async(resolve)()
    websocket.state.django_websocket_auth = auth
    return auth


async def require_websocket_user(websocket: WebSocket) -> AuthUser:
    """Return an authenticated WebSocket user or close with policy violation."""
    auth = await resolve_websocket_auth(websocket)
    if not _is_authenticated(auth.user):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return auth.user


def validate_websocket_origin(websocket: WebSocket) -> None:
    """Validate Host, Origin, and the default same-origin policy."""
    allowed_hosts = list(settings.ALLOWED_HOSTS)
    host_header = websocket.headers.get("host", "").lower()
    host, _port = split_domain_port(host_header)
    origin = websocket.headers.get("origin")
    if not host or not validate_host(host, allowed_hosts):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    if not origin:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    parsed_origin = urlsplit(origin)
    origin_host = parsed_origin.hostname
    if not origin_host:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    if parsed_origin.scheme not in {"http", "https"}:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    if parsed_origin.username is not None or parsed_origin.password is not None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    if (
        parsed_origin.path not in {"", "/"}
        or parsed_origin.query
        or parsed_origin.fragment
    ):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    normalized_origin = (
        f"{parsed_origin.scheme.lower()}://{parsed_origin.netloc.lower()}"
    )
    trusted_origins = _get_websocket_trusted_origins(websocket)
    if normalized_origin in trusted_origins:
        return
    try:
        host_url = urlsplit(f"//{host_header}")
        host_port = host_url.port
        origin_port = parsed_origin.port
    except ValueError as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc
    websocket_scheme = websocket.scope.get("scheme", "ws")
    expected_origin_scheme = "https" if websocket_scheme == "wss" else "http"
    default_port = 443 if expected_origin_scheme == "https" else 80
    effective_origin_port = origin_port if origin_port is not None else default_port
    effective_host_port = host_port if host_port is not None else default_port
    same_origin = (
        parsed_origin.scheme == expected_origin_scheme
        and origin_host == host_url.hostname
        and effective_origin_port == effective_host_port
    )
    if not same_origin or not validate_host(origin_host, allowed_hosts):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)


def _get_websocket_trusted_origins(websocket: WebSocket) -> set[str]:
    config = getattr(websocket.app.state, "django_fastapi_config", None)
    if not isinstance(config, Mapping):
        config = getattr(settings, SETTINGS_NAME, {})
    values = (
        config.get("WEBSOCKET_TRUSTED_ORIGINS", ())
        if isinstance(config, Mapping)
        else ()
    )
    return validate_websocket_config({"WEBSOCKET_TRUSTED_ORIGINS": values})


def validate_websocket_config(config: Mapping[str, Any]) -> set[str]:
    """Validate and normalize configured trusted WebSocket origins."""
    values = config.get("WEBSOCKET_TRUSTED_ORIGINS", ())
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['WEBSOCKET_TRUSTED_ORIGINS'] must be a sequence."
        )
    if not all(isinstance(value, str) for value in values):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['WEBSOCKET_TRUSTED_ORIGINS'] entries must be origins."
        )
    normalized: set[str] = set()
    for value in values:
        parsed = urlsplit(value)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"Invalid WebSocket trusted origin {value!r}."
            ) from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ImproperlyConfigured(f"Invalid WebSocket trusted origin {value!r}.")
        normalized.add(value.lower().rstrip("/"))
    return normalized


def validate_session_middleware(config: Mapping[str, Any]) -> type[Any]:
    """Resolve the optional session hook class at startup, not per request."""
    path = config.get("SESSION_MIDDLEWARE")
    if path is None:
        return SessionMiddleware
    if not isinstance(path, str) or not path:
        raise ImproperlyConfigured("SESSION_MIDDLEWARE must be a dotted class path.")
    try:
        middleware = import_string(path)
    except ImportError as exc:
        raise ImproperlyConfigured("Could not import SESSION_MIDDLEWARE.") from exc
    if not isinstance(middleware, type) or not callable(
        getattr(middleware, "process_request", None)
    ):
        raise ImproperlyConfigured("SESSION_MIDDLEWARE requires process_request.")
    for hook in ("aprocess_request", "aprocess_response"):
        if hasattr(middleware, hook) and not iscoroutinefunction(
            getattr(middleware, hook)
        ):
            raise ImproperlyConfigured(f"SESSION_MIDDLEWARE.{hook} must be async.")
    if not callable(getattr(middleware, "process_response", None)) and not hasattr(
        middleware, "aprocess_response"
    ):
        raise ImproperlyConfigured("SESSION_MIDDLEWARE requires a response hook.")
    return middleware


def validate_auth_resolvers(config: Mapping[str, Any]) -> tuple[AuthResolver, ...]:
    """Import configured auth resolvers and validate they are callables."""
    return tuple(
        _import_auth_resolver(path) for path in _get_auth_resolver_paths(config)
    )


async def _resolve_user(request: Request, django_request: HttpRequest) -> AuthUser:
    for resolver in _get_auth_resolvers(request):
        resolved_user, is_authenticated = await _call_auth_resolver(
            resolver,
            request,
            django_request,
        )
        if resolved_user is not None and is_authenticated:
            return resolved_user
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()


async def _call_auth_resolver(
    resolver: AuthResolver,
    request: Request,
    django_request: HttpRequest,
) -> tuple[AuthResolverResult, bool]:
    if iscoroutinefunction(resolver):
        async_resolver = cast(
            Callable[[Request, HttpRequest], Awaitable[AuthResolverResult]],
            resolver,
        )
        resolved_user = await async_resolver(request, django_request)
        return resolved_user, _is_authenticated(resolved_user)

    return await database_sync_to_async(
        _call_sync_auth_resolver,
        thread_sensitive=True,
    )(resolver, request, django_request)


def _call_sync_auth_resolver(
    resolver: AuthResolver,
    request: Request,
    django_request: HttpRequest,
) -> tuple[AuthResolverResult, bool]:
    sync_resolver = cast(Callable[[Request, HttpRequest], AuthResolverResult], resolver)
    resolved_user = sync_resolver(request, django_request)
    return resolved_user, _is_authenticated(resolved_user)


def _get_auth_resolvers(request: Request) -> tuple[AuthResolver, ...]:
    app_resolvers = getattr(request.app.state, "django_fastapi_auth_resolvers", None)
    if app_resolvers is not None:
        return cast(tuple[AuthResolver, ...], app_resolvers)

    return validate_auth_resolvers(_get_settings_config(request))


def _get_settings_config(request: Request) -> Mapping[str, Any]:
    app_config = getattr(request.app.state, "django_fastapi_config", None)
    if isinstance(app_config, Mapping):
        return cast(Mapping[str, Any], app_config)

    settings_config = getattr(settings, SETTINGS_NAME, {})
    if not isinstance(settings_config, Mapping):
        raise ImproperlyConfigured(f"{SETTINGS_NAME} must be a mapping.")
    return cast(Mapping[str, Any], settings_config)


def _get_auth_resolver_paths(config: Mapping[str, Any]) -> Sequence[str]:
    resolver_paths = config.get("AUTH_RESOLVERS", DEFAULT_AUTH_RESOLVERS)
    if isinstance(resolver_paths, str) or not isinstance(resolver_paths, Sequence):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['AUTH_RESOLVERS'] must be a sequence."
        )
    for resolver_path in resolver_paths:
        if not isinstance(resolver_path, str):
            raise ImproperlyConfigured(
                f"{SETTINGS_NAME}['AUTH_RESOLVERS'] entries must be dotted paths."
            )
    return cast(Sequence[str], resolver_paths)


def _import_auth_resolver(resolver_path: str) -> AuthResolver:
    try:
        resolver = import_string(resolver_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"Could not import FastAPI auth resolver {resolver_path!r}."
        ) from exc
    if not callable(resolver):
        raise ImproperlyConfigured(
            f"{resolver_path!r} is not a callable FastAPI auth resolver."
        )
    return cast(AuthResolver, resolver)


def _is_authenticated(user: AuthResolverResult) -> bool:
    return bool(getattr(user, "is_authenticated", False))
