from __future__ import annotations

from importlib import import_module
from typing import Annotated, Any

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.middleware.csrf import _get_new_csrf_string
from django.test import override_settings
from fastapi import APIRouter, Depends
from starlette.testclient import TestClient

from django_fastapi import create_fastapi_app, csrf_exempt, get_django_request


def _csrf_client(config: dict[str, Any] | None = None) -> TestClient:
    router = APIRouter()

    @router.get("/safe")
    def safe() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/unsafe")
    def unsafe() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/decorator-exempt")
    @csrf_exempt
    def decorator_exempt() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/path-exempt")
    def path_exempt() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/session-touch")
    def session_touch(
        request: Annotated[HttpRequest, Depends(get_django_request)],
    ) -> dict[str, str]:
        request.session["django_fastapi_test"] = "saved"
        return {"status": "ok"}

    app = create_fastapi_app(config or {})
    app.include_router(router)
    return TestClient(app)


def _csrf_headers() -> tuple[dict[str, str], dict[str, str]]:
    csrf_secret = _get_new_csrf_string()
    return (
        {settings.CSRF_COOKIE_NAME: csrf_secret},
        {"X-CSRFToken": csrf_secret},
    )


@pytest.mark.django_db
def test_safe_methods_do_not_require_csrf_token() -> None:
    response = _csrf_client().get("/safe")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_unsafe_methods_require_csrf_token_by_default() -> None:
    response = _csrf_client().post("/unsafe", json={})

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF verification failed."}


@pytest.mark.django_db
def test_unsafe_methods_accept_valid_csrf_token() -> None:
    cookies, headers = _csrf_headers()
    client = _csrf_client()
    client.cookies.update(cookies)
    response = client.post(
        "/unsafe",
        headers=headers,
        json={},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_csrf_can_be_disabled_globally() -> None:
    response = _csrf_client({"CSRF": {"ENABLED": False}}).post("/unsafe", json={})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "config",
    [
        {"CSRF": []},
        {"CSRF": {"ENABLED": "yes"}},
        {"CSRF": {"EXEMPT_PATHS": "/webhook"}},
        {"CSRF": {"EXEMPT_PATHS": [object()]}},
    ],
)
def test_invalid_csrf_config_fails_during_app_creation(config: dict[str, Any]) -> None:
    with pytest.raises(ImproperlyConfigured):
        create_fastapi_app(config)


@pytest.mark.django_db
def test_endpoint_can_be_marked_csrf_exempt() -> None:
    response = _csrf_client().post("/decorator-exempt", json={})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_path_can_be_marked_csrf_exempt() -> None:
    response = _csrf_client(
        {"CSRF": {"EXEMPT_PATHS": ["/path-exempt"]}},
    ).post("/path-exempt", json={})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_django_session_changes_are_saved_on_response() -> None:
    cookies, headers = _csrf_headers()
    client = _csrf_client()
    client.cookies.update(cookies)
    response = client.post(
        "/session-touch",
        headers=headers,
        json={},
    )

    assert response.status_code == 200
    session_key = response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_key
    session_store_class = import_module(settings.SESSION_ENGINE).SessionStore
    session = session_store_class(session_key=session_key)
    assert session["django_fastapi_test"] == "saved"


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.db")
@pytest.mark.django_db(transaction=True)
def test_database_session_changes_are_saved_from_async_middleware() -> None:
    cookies, headers = _csrf_headers()
    client = _csrf_client()
    client.cookies.update(cookies)
    response = client.post(
        "/session-touch",
        headers=headers,
        json={},
    )

    assert response.status_code == 200
    session_key = response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_key
    session_store_class = import_module(settings.SESSION_ENGINE).SessionStore
    session = session_store_class(session_key=session_key)
    assert session["django_fastapi_test"] == "saved"


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.cache")
@pytest.mark.django_db(transaction=True)
def test_cache_session_changes_are_saved_from_async_middleware() -> None:
    cookies, headers = _csrf_headers()
    client = _csrf_client()
    client.cookies.update(cookies)
    response = client.post(
        "/session-touch",
        headers=headers,
        json={},
    )

    assert response.status_code == 200
    session_key = response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert session_key
    session_store_class = import_module(settings.SESSION_ENGINE).SessionStore
    session = session_store_class(session_key=session_key)
    assert session["django_fastapi_test"] == "saved"
