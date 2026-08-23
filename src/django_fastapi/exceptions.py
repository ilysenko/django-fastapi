from __future__ import annotations

from typing import Any, cast

from django.core.exceptions import PermissionDenied
from django.http import Http404
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse


async def django_http404_handler(
    _request: Request,
    exc: Http404,
) -> JSONResponse:
    detail = str(exc) or "Not found."
    return JSONResponse({"detail": detail}, status_code=404)


async def django_permission_denied_handler(
    _request: Request,
    exc: PermissionDenied,
) -> JSONResponse:
    detail = str(exc) or "Forbidden."
    return JSONResponse({"detail": detail}, status_code=403)


def install_django_exception_handlers(app: FastAPI) -> None:
    """Map common Django exceptions to FastAPI JSON responses."""
    app.add_exception_handler(Http404, cast(Any, django_http404_handler))
    app.add_exception_handler(
        PermissionDenied,
        cast(Any, django_permission_denied_handler),
    )
