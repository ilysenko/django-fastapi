from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import ASGIApp

from django_fastapi.fastapi import (
    create_fastapi_app,
    get_fastapi_prefix,
    normalize_mount_path,
)


def mount_django_fastapi_app(
    django_app: ASGIApp,
    fastapi_app: FastAPI | ASGIApp | None = None,
    *,
    prefix: str | None = None,
    name: str = "fastapi",
) -> ASGIApp:
    """Mount a FastAPI ASGI app before falling back to Django."""
    resolved_fastapi_app = fastapi_app or create_fastapi_app()
    resolved_prefix = normalize_mount_path(prefix) if prefix else get_fastapi_prefix()

    return cast(
        ASGIApp,
        Starlette(
            routes=[
                Mount(resolved_prefix, app=resolved_fastapi_app, name=name),
                Mount("/", app=django_app, name="django"),
            ],
        ),
    )


def mount_fastapi_app(
    django_app: ASGIApp,
    fastapi_app: FastAPI | ASGIApp,
    *,
    path: str = "/fastapi",
    name: str = "fastapi",
) -> ASGIApp:
    """Backward-compatible alias for manually mounting a FastAPI app."""
    return mount_django_fastapi_app(
        django_app,
        fastapi_app,
        prefix=path,
        name=name,
    )


def get_django_fastapi_application(
    fastapi_app: FastAPI | ASGIApp | None = None,
    *,
    prefix: str | None = None,
    name: str = "fastapi",
) -> ASGIApp:
    """Create Django's ASGI app and mount a FastAPI app beside it."""
    from django.core.asgi import get_asgi_application

    return mount_django_fastapi_app(
        cast(ASGIApp, get_asgi_application()),
        fastapi_app,
        prefix=prefix,
        name=name,
    )
