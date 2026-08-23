from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from inspect import iscoroutinefunction
from io import BytesIO
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string
from fastapi import Depends, HTTPException, Request, status

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


def _empty_response(_request: HttpRequest) -> HttpResponseBase:
    return HttpResponse()


async def get_django_request(request: Request) -> HttpRequest:
    """Build and cache a Django-compatible request for a FastAPI request."""
    existing_request = getattr(request.state, "django_request", None)
    if existing_request is not None:
        return cast(HttpRequest, existing_request)

    django_request = ASGIRequest(request.scope, BytesIO(await request.body()))
    session_middleware = SessionMiddleware(_empty_response)
    session_middleware.process_request(django_request)
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

    return await sync_to_async(
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
