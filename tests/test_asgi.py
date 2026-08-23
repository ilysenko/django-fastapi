from __future__ import annotations

import sys
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured
from fastapi import APIRouter, FastAPI
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from django_fastapi import (
    create_fastapi_app,
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
