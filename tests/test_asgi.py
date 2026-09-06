from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured
from fastapi import APIRouter, FastAPI, WebSocket
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from django_fastapi import (
    create_fastapi_app,
    create_websocket_app,
    get_fastapi_prefix,
    mount_django_fastapi_app,
    mount_fastapi_app,
)

ROUTER_MODULE_NAME = "django_fastapi_test_routers"


async def django_fallback(scope: Scope, receive: Receive, send: Send) -> None:
    request = Request(scope, receive)
    response = PlainTextResponse(f"django:{request.url.path}")
    await response(scope, receive, send)


@pytest.fixture(name="router_module")
def fixture_router_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    router_module = ModuleType(ROUTER_MODULE_NAME)

    sync_router = APIRouter(prefix="/sync")

    @sync_router.get("/health")
    def sync_health() -> dict[str, str]:
        return {"mode": "sync"}

    async_router = APIRouter(prefix="/async")

    @async_router.get("/health")
    async def async_health() -> dict[str, str]:
        return {"mode": "async"}

    router_module.sync_router = sync_router
    router_module.async_router = async_router
    router_module.not_router = object()

    websocket_router = APIRouter()

    @websocket_router.websocket("/")
    async def websocket_health(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"mode": "websocket"})
        await websocket.close()

    router_module.websocket_router = websocket_router

    def app_configurator(app: FastAPI) -> None:
        app.state.configured_by_test = True

    router_module.app_configurator = app_configurator
    router_module.not_configurator = object()
    monkeypatch.setitem(sys.modules, ROUTER_MODULE_NAME, router_module)
    return router_module


def test_create_fastapi_app_includes_configured_routers(
    router_module: ModuleType,
) -> None:
    app = create_fastapi_app(
        {
            "TITLE": "Test API",
            "ROUTERS": [
                f"{router_module.__name__}.sync_router",
                f"{router_module.__name__}.async_router",
            ],
        }
    )
    client = TestClient(app)

    assert app.title == "Test API"
    assert client.get("/sync/health").json() == {"mode": "sync"}
    assert client.get("/async/health").json() == {"mode": "async"}


def test_create_fastapi_app_rejects_invalid_router_object(
    router_module: ModuleType,
) -> None:
    with pytest.raises(ImproperlyConfigured, match="APIRouter"):
        create_fastapi_app({"ROUTERS": [f"{router_module.__name__}.not_router"]})


def test_create_fastapi_app_rejects_missing_router_path() -> None:
    with pytest.raises(ImproperlyConfigured, match="Could not import"):
        create_fastapi_app({"ROUTERS": ["missing.module.router"]})


def test_create_websocket_app_uses_separate_router_config(
    router_module: ModuleType,
) -> None:
    app = create_websocket_app(
        {
            "ROUTERS": [f"{router_module.__name__}.sync_router"],
            "WEBSOCKET_ROUTERS": [f"{router_module.__name__}.websocket_router"],
        }
    )
    client = TestClient(app)

    assert client.get("/sync/health").status_code == 404
    with client.websocket_connect("/") as websocket:
        assert websocket.receive_json() == {"mode": "websocket"}


def test_create_fastapi_app_runs_configured_app_configurators(
    router_module: ModuleType,
) -> None:
    app = create_fastapi_app(
        {
            "APP_CONFIGURATORS": [
                f"{router_module.__name__}.app_configurator",
            ],
        }
    )

    assert app.state.configured_by_test is True


def test_create_fastapi_app_rejects_invalid_app_configurator(
    router_module: ModuleType,
) -> None:
    with pytest.raises(ImproperlyConfigured, match="app configurator"):
        create_fastapi_app(
            {
                "APP_CONFIGURATORS": [
                    f"{router_module.__name__}.not_configurator",
                ],
            }
        )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"FASTAPI_KWARGS": []}, "FASTAPI_KWARGS"),
        ({"ROUTERS": "module.router"}, "ROUTERS"),
        ({"ROUTERS": [object()]}, "ROUTERS"),
        ({"APP_CONFIGURATORS": "module.configure"}, "APP_CONFIGURATORS"),
        ({"APP_CONFIGURATORS": [object()]}, "APP_CONFIGURATORS"),
        ({"SESSION_MIDDLEWARE": 43}, "SESSION_MIDDLEWARE"),
        ({"SESSION_MIDDLEWARE": "missing.module.middleware"}, "SESSION_MIDDLEWARE"),
        ({"SESSION_MIDDLEWARE": "builtins.dict"}, "SESSION_MIDDLEWARE"),
        (
            {"APP_CONFIGURATORS": ["missing.module.configure"]},
            "Could not import",
        ),
    ],
)
def test_create_fastapi_app_validates_startup_configuration(
    config: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        create_fastapi_app(config)


@pytest.mark.parametrize(
    "trusted_origins",
    [
        "https://app.example",
        [object()],
        ["ftp://app.example"],
        ["https://user@app.example"],
        ["https://app.example/path"],
        ["https://app.example:invalid"],
    ],
)
def test_create_websocket_app_rejects_invalid_trusted_origins(
    trusted_origins: object,
) -> None:
    with pytest.raises(ImproperlyConfigured, match="[Oo][Rr][Ii][Gg][Ii][Nn]"):
        create_websocket_app({"WEBSOCKET_TRUSTED_ORIGINS": trusted_origins})


def test_get_fastapi_prefix_normalizes_settings() -> None:
    assert get_fastapi_prefix({"PREFIX": "api-next/"}) == "/api-next"


def test_mounts_fastapi_before_django_fallback() -> None:
    fastapi_app = FastAPI()

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app = mount_fastapi_app(django_fallback, fastapi_app, path="/async/fastapi")
    client = TestClient(app)

    assert client.get("/async/fastapi/health").json() == {"status": "ok"}
    assert client.get("/legacy").text == "django:/legacy"


def test_mount_django_fastapi_app_uses_configured_prefix(
    router_module: ModuleType,
) -> None:
    app = mount_django_fastapi_app(
        django_fallback,
        create_fastapi_app({"ROUTERS": [f"{router_module.__name__}.sync_router"]}),
        prefix="api-next",
    )
    client = TestClient(app)

    assert client.get("/api-next/sync/health").json() == {"mode": "sync"}
    assert client.get("/legacy").text == "django:/legacy"


def test_mount_path_may_omit_leading_slash() -> None:
    fastapi_app = FastAPI()

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app = mount_fastapi_app(django_fallback, fastapi_app, path="fastapi")
    client = TestClient(app)

    assert client.get("/fastapi/health").json() == {"status": "ok"}


def test_mount_path_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="mount path"):
        mount_fastapi_app(django_fallback, FastAPI(), path=" ")


def test_exact_websocket_mount_and_controlled_fallback() -> None:
    websocket_app = FastAPI()

    @websocket_app.websocket("/")
    async def websocket_echo(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("connected")
        await websocket.close()

    app = mount_django_fastapi_app(
        django_fallback,
        FastAPI(),
        websocket_app=websocket_app,
        websocket_path="/ws",
    )
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "connected"
    with pytest.raises(Exception) as rejected, client.websocket_connect("/legacy"):
        pass
    assert getattr(rejected.value, "code", None) == 1008
    with (
        pytest.raises(Exception) as nested_rejected,
        client.websocket_connect("/ws/nested"),
    ):
        pass
    assert getattr(nested_rejected.value, "code", None) == 1008


@pytest.mark.parametrize("with_state", [True, False])
def test_root_and_fastapi_lifespans_run_once(with_state: bool) -> None:
    calls: list[str] = []

    @asynccontextmanager
    async def http_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        calls.append("http-start")
        yield
        calls.append("http-stop")

    @asynccontextmanager
    async def root_lifespan(_app: object) -> AsyncIterator[None]:
        calls.append("root-start")
        yield
        calls.append("root-stop")

    app = mount_django_fastapi_app(
        django_fallback,
        FastAPI(lifespan=http_lifespan),
        lifespan=root_lifespan,
    )
    if with_state:
        with TestClient(app):
            assert calls == ["root-start", "http-start"]
    else:
        messages: list[Message] = []

        async def receive() -> Message:
            if not messages:
                return {"type": "lifespan.startup"}
            assert calls == ["root-start", "http-start"]
            return {"type": "lifespan.shutdown"}

        async def send(message: Message) -> None:
            messages.append(message)

        asyncio.run(app({"type": "lifespan"}, receive, send))
        assert [message["type"] for message in messages] == [
            "lifespan.startup.complete",
            "lifespan.shutdown.complete",
        ]

    assert calls == ["root-start", "http-start", "http-stop", "root-stop"]


def test_root_and_fastapi_lifespan_state_is_merged() -> None:
    @asynccontextmanager
    async def http_lifespan(
        _app: FastAPI,
    ) -> AsyncIterator[dict[str, str]]:
        yield {"http": "ready", "shared": "http"}

    @asynccontextmanager
    async def root_lifespan(
        _app: object,
    ) -> AsyncIterator[dict[str, str]]:
        yield {"root": "ready", "shared": "root"}

    fastapi_app = FastAPI(lifespan=http_lifespan)

    @fastapi_app.get("/state")
    async def lifespan_state(request: Request) -> dict[str, str]:
        return {
            "http": request.state.http,
            "root": request.state.root,
            "shared": request.state.shared,
        }

    app = mount_django_fastapi_app(
        django_fallback,
        fastapi_app,
        prefix="/api",
        lifespan=root_lifespan,
    )

    with TestClient(app) as client:
        assert client.get("/api/state").json() == {
            "http": "ready",
            "root": "ready",
            "shared": "root",
        }


def test_websocket_app_respects_discovery_configuration():
    app = create_websocket_app(
        {
            "FASTAPI_KWARGS": {
                "docs_url": None,
                "redoc_url": None,
                "openapi_url": None,
            }
        }
    )
    client = TestClient(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
