from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import BaseRoute, Match, Mount, WebSocketRoute
from starlette.types import ASGIApp, Lifespan

from django_fastapi.fastapi import (
    create_fastapi_app,
    get_fastapi_prefix,
    normalize_mount_path,
)


class _ExactWebSocketRoute(BaseRoute):
    def __init__(self, path: str, app: ASGIApp, name: str) -> None:
        self.path = path
        self.app = app
        self.name = name

    def matches(self, scope: Any) -> tuple[Match, dict[str, Any]]:
        root_path = scope.get("root_path", "")
        route_path = scope["path"].removeprefix(root_path)
        if scope["type"] == "websocket" and route_path == self.path:
            return Match.FULL, {"endpoint": self.app}
        return Match.NONE, {}

    async def handle(self, scope: Any, receive: Any, send: Any) -> None:
        child_scope = dict(scope)
        root_path = scope.get("root_path", "")
        route_path = scope["path"].removeprefix(root_path)
        child_scope["root_path"] = root_path + route_path
        child_scope["path"] = "/"
        child_scope["raw_path"] = b"/"
        await self.app(child_scope, receive, send)


class _RejectWebSocket:
    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await send(
            {"type": "websocket.close", "code": 1008, "reason": "Unsupported path"}
        )


def mount_django_fastapi_app(
    django_app: ASGIApp,
    fastapi_app: FastAPI | ASGIApp | None = None,
    *,
    prefix: str | None = None,
    name: str = "fastapi",
    websocket_app: FastAPI | ASGIApp | None = None,
    websocket_path: str = "/ws",
    lifespan: Callable[[Starlette], Any] | None = None,
    root_routes: Sequence[BaseRoute] = (),
) -> ASGIApp:
    """Mount a FastAPI ASGI app before falling back to Django."""
    resolved_fastapi_app = fastapi_app or create_fastapi_app()
    resolved_prefix = normalize_mount_path(prefix) if prefix else get_fastapi_prefix()

    routes: list[BaseRoute] = list(root_routes)
    if websocket_app is not None:
        routes.append(
            _ExactWebSocketRoute(
                normalize_mount_path(websocket_path),
                websocket_app,
                name="websocket",
            )
        )
    routes.append(WebSocketRoute("/{path:path}", _RejectWebSocket()))
    routes.extend(
        [
            Mount(resolved_prefix, app=resolved_fastapi_app, name=name),
            Mount("/", app=django_app, name="django"),
        ]
    )

    @asynccontextmanager
    async def root_lifespan(
        app: Starlette,
    ) -> AsyncIterator[Mapping[str, Any] | None]:
        async with AsyncExitStack() as stack:
            root_state = None
            if lifespan is not None:
                root_state = await stack.enter_async_context(lifespan(app))
            http_state = None
            fastapi_lifespan = getattr(resolved_fastapi_app, "router", None)
            if fastapi_lifespan is not None:
                http_state = await stack.enter_async_context(
                    fastapi_lifespan.lifespan_context(resolved_fastapi_app)
                )
            if root_state is None and http_state is None:
                yield None
            else:
                yield {**(http_state or {}), **(root_state or {})}

    return cast(
        ASGIApp,
        Starlette(
            routes=routes,
            # Starlette types stateful/stateless factories as a union; this
            # factory supports both, including servers without lifespan state.
            lifespan=cast(Lifespan[Starlette], root_lifespan),
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
    websocket_app: FastAPI | ASGIApp | None = None,
    websocket_path: str = "/ws",
    lifespan: Callable[[Starlette], Any] | None = None,
    root_routes: Sequence[BaseRoute] = (),
) -> ASGIApp:
    """Create Django's ASGI app and mount a FastAPI app beside it."""
    from django.core.asgi import get_asgi_application

    return mount_django_fastapi_app(
        cast(ASGIApp, get_asgi_application()),
        fastapi_app,
        prefix=prefix,
        name=name,
        websocket_app=websocket_app,
        websocket_path=websocket_path,
        lifespan=lifespan,
        root_routes=root_routes,
    )
