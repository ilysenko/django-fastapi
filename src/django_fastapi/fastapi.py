from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from fastapi import APIRouter, Depends, FastAPI

from django_fastapi.auth import (
    validate_auth_resolvers,
    validate_session_middleware,
    validate_websocket_config,
)
from django_fastapi.csrf import require_csrf, validate_csrf_config
from django_fastapi.database import DjangoHTTPMiddleware
from django_fastapi.exceptions import install_django_exception_handlers

DEFAULT_PREFIX = "/api"
DEFAULT_TITLE = "Django FastAPI"
SETTINGS_NAME = "DJANGO_FASTAPI"
AppConfigurator = Callable[[FastAPI], object]


def create_fastapi_app(config: Mapping[str, Any] | None = None) -> FastAPI:
    """Create a FastAPI app from Django settings or an explicit config."""
    resolved_config = _resolve_config(config)
    validate_csrf_config(resolved_config)
    fastapi_kwargs = _get_mapping(resolved_config, "FASTAPI_KWARGS")
    fastapi_kwargs.setdefault("title", str(resolved_config.get("TITLE", DEFAULT_TITLE)))
    fastapi_kwargs["dependencies"] = [
        *list(fastapi_kwargs.get("dependencies") or []),
        Depends(require_csrf),
    ]

    app = FastAPI(**fastapi_kwargs)
    app.state.django_fastapi_config = dict(resolved_config)
    app.state.django_fastapi_auth_resolvers = validate_auth_resolvers(resolved_config)
    app.state.django_fastapi_session_middleware = validate_session_middleware(
        resolved_config
    )
    app.add_middleware(DjangoHTTPMiddleware)
    install_django_exception_handlers(app)
    for configurator in _get_app_configurators(resolved_config):
        configurator(app)
    for router_path in _get_router_paths(resolved_config):
        app.include_router(_import_router(router_path))
    return app


def create_websocket_app(config: Mapping[str, Any] | None = None) -> FastAPI:
    """Create a CSRF-free FastAPI app for configured WebSocket routers."""
    resolved_config = _resolve_config(config)
    validate_websocket_config(resolved_config)
    # Carry FASTAPI_KWARGS here too. Without it this app keeps FastAPI's default
    # /docs, /redoc and /openapi.json, and only the websocket-scope mount keeps
    # them unreachable -- protection that lives in the routing rather than in
    # the configuration, and that a change to a plain Mount would remove.
    fastapi_kwargs = _get_mapping(resolved_config, "FASTAPI_KWARGS")
    fastapi_kwargs["title"] = (
        f"{resolved_config.get('TITLE', DEFAULT_TITLE)} WebSockets"
    )
    fastapi_kwargs.pop("dependencies", None)
    app = FastAPI(**fastapi_kwargs)
    app.state.django_fastapi_config = dict(resolved_config)
    for router_path in _get_router_paths(resolved_config, key="WEBSOCKET_ROUTERS"):
        app.include_router(_import_router(router_path))
    return app


def get_fastapi_prefix(config: Mapping[str, Any] | None = None) -> str:
    """Return the configured FastAPI ASGI mount prefix."""
    resolved_config = _resolve_config(config)
    return normalize_mount_path(str(resolved_config.get("PREFIX", DEFAULT_PREFIX)))


def normalize_mount_path(path: str) -> str:
    """Normalize a Starlette mount path."""
    mount_path = path.strip()
    if not mount_path:
        raise ValueError("FastAPI mount path cannot be empty.")
    if not mount_path.startswith("/"):
        mount_path = f"/{mount_path}"
    return mount_path.rstrip("/") or "/"


def _resolve_config(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if config is not None:
        return config

    settings_config = getattr(settings, SETTINGS_NAME, {})
    if not isinstance(settings_config, Mapping):
        raise ImproperlyConfigured(f"{SETTINGS_NAME} must be a mapping.")
    return cast(Mapping[str, Any], settings_config)


def _get_mapping(config: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key, {})
    if not isinstance(value, Mapping):
        raise ImproperlyConfigured(f"{SETTINGS_NAME}[{key!r}] must be a mapping.")
    return dict(value)


def _get_router_paths(
    config: Mapping[str, Any], *, key: str = "ROUTERS"
) -> Sequence[str]:
    router_paths = config.get(key, ())
    if isinstance(router_paths, str) or not isinstance(router_paths, Sequence):
        raise ImproperlyConfigured(f"{SETTINGS_NAME}[{key!r}] must be a sequence.")
    for router_path in router_paths:
        if not isinstance(router_path, str):
            raise ImproperlyConfigured(
                f"{SETTINGS_NAME}[{key!r}] entries must be dotted paths."
            )
    return cast(Sequence[str], router_paths)


def _import_router(router_path: str) -> APIRouter:
    try:
        router = import_string(router_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"Could not import FastAPI router {router_path!r}."
        ) from exc
    if not isinstance(router, APIRouter):
        raise ImproperlyConfigured(f"{router_path!r} is not a FastAPI APIRouter.")
    return router


def _get_app_configurators(config: Mapping[str, Any]) -> tuple[AppConfigurator, ...]:
    configurator_paths = config.get("APP_CONFIGURATORS", ())
    if isinstance(configurator_paths, str) or not isinstance(
        configurator_paths,
        Sequence,
    ):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['APP_CONFIGURATORS'] must be a sequence."
        )
    return tuple(
        _import_app_configurator(configurator_path)
        for configurator_path in configurator_paths
    )


def _import_app_configurator(configurator_path: object) -> AppConfigurator:
    if not isinstance(configurator_path, str):
        raise ImproperlyConfigured(
            f"{SETTINGS_NAME}['APP_CONFIGURATORS'] entries must be dotted paths."
        )
    try:
        configurator = import_string(configurator_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"Could not import FastAPI app configurator {configurator_path!r}."
        ) from exc
    if not callable(configurator):
        raise ImproperlyConfigured(
            f"{configurator_path!r} is not a callable FastAPI app configurator."
        )
    return cast(AppConfigurator, configurator)
