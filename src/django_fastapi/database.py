"""Thread-owned Django connection boundaries for ASGI applications."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from inspect import (
    isasyncgenfunction,
    iscoroutinefunction,
    isgeneratorfunction,
    signature,
)
from typing import Any, ParamSpec, TypeVar, cast

from anyio import CancelScope
from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.db import connections
from django.http import HttpResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

P = ParamSpec("P")
R = TypeVar("R")


def close_db_connections(*, obsolete_only: bool = False) -> None:
    """Release request-scoped leases while preserving configured persistent ones."""
    for connection in connections.all(initialized_only=True):
        if connection.in_atomic_block:
            continue
        if obsolete_only or connection.settings_dict.get("CONN_MAX_AGE", 0) != 0:
            connection.close_if_unusable_or_obsolete()
        else:
            connection.close()


async def aclose_db_connections() -> None:
    """Release thread-sensitive leases, including during cancellation."""
    # Starlette streaming uses AnyIO level cancellation: shielding only with
    # asyncio would still cancel every subsequent await in an expired scope.
    with CancelScope(shield=True):
        cleanup = asyncio.ensure_future(sync_to_async(close_db_connections)())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            # Don't destroy the request executor before queued cleanup completes.
            await cleanup
            raise


def django_db(func: Callable[P, R]) -> Callable[P, R]:
    """Bound a synchronous ORM unit, including a FastAPI handler or dependency.

    Materialize querysets and response schemas inside the unit. Nested atomic
    blocks retain their connection until their owning outer boundary exits.
    """
    if (
        isgeneratorfunction(func)
        or isasyncgenfunction(func)
        or iscoroutinefunction(func)
    ):
        raise TypeError("django_db requires a synchronous, non-generator function")

    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        close_db_connections(obsolete_only=True)
        try:
            return func(*args, **kwargs)
        finally:
            close_db_connections()

    # FastAPI must resolve postponed annotations in the original module, not here.
    try:
        resolved_signature = signature(func, eval_str=True)
    except NameError:
        # Non-handler ORM helpers may use TYPE_CHECKING-only annotations.
        resolved_signature = signature(func)
    cast(Any, wrapped).__signature__ = resolved_signature
    cast(Any, wrapped).__django_db__ = True
    return wrapped


def database_sync_to_async(
    func: Callable[P, R],
    *,
    thread_sensitive: bool = True,
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Run a synchronous ORM unit and release its connections in the same thread."""
    return sync_to_async(django_db(func), thread_sensitive=thread_sensitive)


class DjangoHTTPMiddleware:
    """Own HTTP ORM leases and session response handling without buffering streams."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async with ThreadSensitiveContext():  # type: ignore[no-untyped-call]

            async def send_response(message: Message) -> None:
                if message["type"] == "http.response.start":
                    state = scope.get("state", {})
                    request = state.get("django_request")
                    middleware = state.get("django_session_middleware")
                    if request is not None and middleware is not None:
                        response = HttpResponse(status=message["status"])
                        headers = MutableHeaders(scope=message)
                        # Django's response is a session-only scratch object:
                        # copying raw headers through its dict would collapse
                        # Set-Cookie and invent Content-Type for 204/304.
                        original_vary = ", ".join(headers.getlist("vary"))
                        if original_vary:
                            response["Vary"] = original_vary
                        if hasattr(middleware, "aprocess_response"):
                            response = await middleware.aprocess_response(
                                request, response
                            )
                        else:
                            response = await database_sync_to_async(
                                middleware.process_response,
                            )(request, response)
                        if response.get("Vary", "") != original_vary:
                            headers["Vary"] = response["Vary"]
                        for morsel in response.cookies.values():
                            headers.append("set-cookie", morsel.OutputString())
                    # In particular, don't hold the initial request lease while
                    # an SSE iterator waits for an LLM or the downstream client.
                    await aclose_db_connections()
                await send(message)

            try:
                await self.app(scope, receive, send_response)
            finally:
                await aclose_db_connections()
