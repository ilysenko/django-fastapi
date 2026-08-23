from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, TypeVar, cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.middleware.csrf import CsrfViewMiddleware
from fastapi import Depends, HTTPException, Request, status

from django_fastapi.auth import get_django_request

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
DEFAULT_CSRF_CONFIG = {"ENABLED": True, "EXEMPT_PATHS": ()}
SETTINGS_NAME = "DJANGO_FASTAPI"

CallableT = TypeVar("CallableT", bound=Callable[..., Any])


def csrf_exempt(func: CallableT) -> CallableT:
    """Mark a FastAPI path operation as exempt from Django CSRF checks."""
    cast(Any, func).django_fastapi_csrf_exempt = True
    return func


async def require_csrf(
    request: Request,
    django_request: Annotated[HttpRequest, Depends(get_django_request)],
) -> None:
    """Require Django CSRF validation for unsafe FastAPI requests by default."""
    if not is_csrf_enabled(_get_settings_config(request)):
        return
    if request.method.upper() in SAFE_METHODS:
        return
    if _endpoint_is_exempt(request):
        return
    if _path_is_exempt(request, django_request):
        return

    endpoint = cast(Callable[..., HttpResponseBase], request.scope.get("endpoint"))
    response = CsrfViewMiddleware(_empty_response).process_view(
        django_request,
        endpoint,
        (),
        {},
    )
    if response is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF verification failed.",
        )


def is_csrf_enabled(config: Mapping[str, Any]) -> bool:
    """Return whether CSRF protection is enabled for a django-fastapi config."""
    csrf_config = _get_csrf_config(config)
    enabled = csrf_config.get("ENABLED", True)
    if not isinstance(enabled, bool):
        raise ImproperlyConfigured(f"{SETTINGS_NAME}['CSRF']['ENABLED'] must be bool.")
    return enabled


def validate_csrf_config(config: Mapping[str, Any]) -> None:
    """Validate the CSRF configuration before the FastAPI app starts."""
    is_csrf_enabled(config)
    get_csrf_exempt_paths(config)


def get_csrf_exempt_paths(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Return configured CSRF-exempt request paths."""
    csrf_config = _get_csrf_config(config)
    exempt_paths = csrf_config.get("EXEMPT_PATHS", ())
    if isinstance(exempt_paths, str) or not isinstance(exempt_paths, Sequence):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['CSRF']['EXEMPT_PATHS'] must be a sequence."
        )
    for path in exempt_paths:
        if not isinstance(path, str):
            raise ImproperlyConfigured(
                f"{SETTINGS_NAME}['CSRF']['EXEMPT_PATHS'] entries must be strings."
            )
    return tuple(_normalize_path(path) for path in cast(Sequence[str], exempt_paths))


def _empty_response(_request: HttpRequest) -> HttpResponseBase:
    return HttpResponse()


def _get_settings_config(request: Request) -> Mapping[str, Any]:
    app_config = getattr(request.app.state, "django_fastapi_config", None)
    if isinstance(app_config, Mapping):
        return cast(Mapping[str, Any], app_config)

    settings_config = getattr(settings, SETTINGS_NAME, {})
    if not isinstance(settings_config, Mapping):
        raise ImproperlyConfigured(f"{SETTINGS_NAME} must be a mapping.")
    return cast(Mapping[str, Any], settings_config)


def _get_csrf_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    csrf_config = config.get("CSRF", DEFAULT_CSRF_CONFIG)
    if not isinstance(csrf_config, Mapping):
        raise ImproperlyConfigured(f"{SETTINGS_NAME}['CSRF'] must be a mapping.")
    return cast(Mapping[str, Any], csrf_config)


def _endpoint_is_exempt(request: Request) -> bool:
    endpoint = request.scope.get("endpoint")
    return bool(getattr(endpoint, "django_fastapi_csrf_exempt", False))


def _path_is_exempt(request: Request, django_request: HttpRequest) -> bool:
    exempt_paths = get_csrf_exempt_paths(_get_settings_config(request))
    if not exempt_paths:
        return False

    request_paths = {
        _normalize_path(str(request.url.path)),
        _normalize_path(django_request.path),
    }
    root_path = str(request.scope.get("root_path") or "")
    if root_path:
        relative_path = str(request.url.path).removeprefix(root_path) or "/"
        request_paths.add(_normalize_path(relative_path))

    return any(path in exempt_paths for path in request_paths)


def _normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"
