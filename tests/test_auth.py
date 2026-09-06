from __future__ import annotations

import sys
from types import ModuleType
from typing import Annotated, Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, override_settings
from fastapi import APIRouter, Depends, FastAPI, Request, WebSocket
from starlette.testclient import TestClient

from django_fastapi import (
    create_fastapi_app,
    get_authenticated_user,
    get_current_staff_user,
    get_current_user,
    get_django_request,
    resolve_websocket_auth,
    validate_websocket_origin,
)

AUTH_MODULE_NAME = "django_fastapi_test_auth_resolvers"


@pytest.fixture(name="auth_module")
def fixture_auth_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    auth_module = ModuleType(AUTH_MODULE_NAME)
    monkeypatch.setitem(sys.modules, AUTH_MODULE_NAME, auth_module)
    return auth_module


def _create_user(username: str, *, is_staff: bool = False) -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="not-a-real-password",
        is_staff=is_staff,
    )


def _session_cookie_for(user: Any) -> tuple[str, str]:
    from django.conf import settings

    django_client = Client()
    django_client.force_login(user)
    session_cookie = django_client.cookies[settings.SESSION_COOKIE_NAME]
    return settings.SESSION_COOKIE_NAME, session_cookie.value


def _auth_client(config: dict[str, Any] | None = None) -> TestClient:
    router = APIRouter()

    @router.get("/current")
    def current_user(
        user: Annotated[Any, Depends(get_current_user)],
    ) -> dict[str, Any]:
        return {
            "authenticated": bool(user.is_authenticated),
            "username": getattr(user, "username", ""),
        }

    @router.get("/private")
    def private_user(
        user: Annotated[Any, Depends(get_authenticated_user)],
    ) -> dict[str, str]:
        return {"username": user.username}

    @router.get("/staff")
    def staff_user(
        user: Annotated[Any, Depends(get_current_staff_user)],
    ) -> dict[str, str]:
        return {"username": user.username}

    @router.get("/request-cache")
    async def request_cache(request: Request) -> dict[str, bool]:
        first_request = await get_django_request(request)
        second_request = await get_django_request(request)
        return {
            "same_request": first_request is second_request,
            "has_session": hasattr(first_request, "session"),
        }

    app = create_fastapi_app(config or {})
    app.include_router(router)
    return TestClient(app)


@pytest.mark.django_db(transaction=True)
def test_current_user_defaults_to_anonymous_user() -> None:
    response = _auth_client().get("/current")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "username": ""}


@pytest.mark.django_db(transaction=True)
def test_django_session_cookie_resolves_logged_in_user() -> None:
    user = _create_user("session-user")
    cookie_name, cookie_value = _session_cookie_for(user)
    client = _auth_client()
    client.cookies.set(cookie_name, cookie_value)

    response = client.get("/current")

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": "session-user"}


@pytest.mark.django_db(transaction=True)
def test_custom_authorization_resolver_can_resolve_user(
    auth_module: ModuleType,
) -> None:
    user = _create_user("token-user")

    async def token_resolver(request: Request, _django_request: Any) -> Any | None:
        if request.headers.get("authorization") == "Bearer test-token":
            return user
        return None

    auth_module.token_resolver = token_resolver
    client = _auth_client(
        {"AUTH_RESOLVERS": [f"{auth_module.__name__}.token_resolver"]}
    )

    response = client.get("/current", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": "token-user"}


@pytest.mark.parametrize(
    "resolvers",
    ["module.resolver", [object()], ["missing.module.resolver"]],
)
def test_create_fastapi_app_rejects_invalid_auth_resolvers(
    resolvers: object,
) -> None:
    with pytest.raises(ImproperlyConfigured):
        create_fastapi_app({"AUTH_RESOLVERS": resolvers})


def test_create_fastapi_app_rejects_non_callable_auth_resolver(
    auth_module: ModuleType,
) -> None:
    auth_module.not_callable = object()
    with pytest.raises(ImproperlyConfigured, match="callable"):
        create_fastapi_app({"AUTH_RESOLVERS": [f"{auth_module.__name__}.not_callable"]})


@pytest.mark.django_db(transaction=True)
def test_auth_resolver_ordering_uses_first_authenticated_user(
    auth_module: ModuleType,
) -> None:
    user = _create_user("ordered-user")
    calls: list[str] = []

    def first_resolver(_request: Request, _django_request: Any) -> AnonymousUser:
        calls.append("first")
        return AnonymousUser()

    def second_resolver(_request: Request, _django_request: Any) -> Any:
        calls.append("second")
        return user

    def third_resolver(_request: Request, _django_request: Any) -> Any:
        calls.append("third")
        return user

    auth_module.first_resolver = first_resolver
    auth_module.second_resolver = second_resolver
    auth_module.third_resolver = third_resolver
    client = _auth_client(
        {
            "AUTH_RESOLVERS": [
                f"{auth_module.__name__}.first_resolver",
                f"{auth_module.__name__}.second_resolver",
                f"{auth_module.__name__}.third_resolver",
            ],
        }
    )

    response = client.get("/current")

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": "ordered-user"}
    assert calls == ["first", "second"]


@pytest.mark.django_db(transaction=True)
def test_get_authenticated_user_returns_401_for_anonymous_user() -> None:
    response = _auth_client().get("/private")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


@pytest.mark.django_db(transaction=True)
def test_get_current_staff_user_returns_403_for_non_staff_user() -> None:
    user = _create_user("regular-user")
    cookie_name, cookie_value = _session_cookie_for(user)
    client = _auth_client()
    client.cookies.set(cookie_name, cookie_value)

    response = client.get("/staff")

    assert response.status_code == 403
    assert response.json() == {"detail": "Staff access required."}


@pytest.mark.django_db(transaction=True)
def test_get_current_staff_user_accepts_staff_user() -> None:
    user = _create_user("staff-user", is_staff=True)
    cookie_name, cookie_value = _session_cookie_for(user)
    client = _auth_client()
    client.cookies.set(cookie_name, cookie_value)

    response = client.get("/staff")

    assert response.status_code == 200
    assert response.json() == {"username": "staff-user"}


@pytest.mark.django_db(transaction=True)
def test_get_django_request_is_cached_per_fastapi_request() -> None:
    response = _auth_client().get("/request-cache")

    assert response.status_code == 200
    assert response.json() == {"same_request": True, "has_session": True}


@pytest.mark.django_db(transaction=True)
def test_websocket_auth_resolves_session_user_and_anonymous_session() -> None:
    user = _create_user("websocket-user")
    cookie_name, cookie_value = _session_cookie_for(user)
    app = FastAPI()

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        auth = await resolve_websocket_auth(websocket)
        await websocket.accept()
        await websocket.send_json(
            {
                "authenticated": bool(auth.user.is_authenticated),
                "username": getattr(auth.user, "username", ""),
                "has_session": bool(auth.session_key),
                "scheme": auth.request.scheme,
                "is_secure": auth.request.is_secure(),
                "absolute_uri": auth.request.build_absolute_uri("/account"),
            }
        )
        await websocket.close()

    client = TestClient(app)
    client.cookies.set(cookie_name, cookie_value)
    with client.websocket_connect(
        "/ws", headers={"origin": "http://testserver"}
    ) as websocket:
        assert websocket.receive_json() == {
            "authenticated": True,
            "username": "websocket-user",
            "has_session": True,
            "scheme": "http",
            "is_secure": False,
            "absolute_uri": "http://testserver/account",
        }


@pytest.mark.django_db(transaction=True)
def test_secure_websocket_auth_builds_secure_django_request() -> None:
    app = FastAPI()

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        auth = await resolve_websocket_auth(websocket)
        await websocket.accept()
        await websocket.send_json(
            {
                "scheme": auth.request.scheme,
                "is_secure": auth.request.is_secure(),
                "absolute_uri": auth.request.build_absolute_uri("/account"),
            }
        )
        await websocket.close()

    client = TestClient(app)
    with client.websocket_connect(
        "wss://testserver/ws",
        headers={"origin": "https://testserver"},
    ) as websocket:
        assert websocket.receive_json() == {
            "scheme": "https",
            "is_secure": True,
            "absolute_uri": "https://testserver/account",
        }


def test_websocket_origin_rejects_untrusted_origin() -> None:
    app = FastAPI()

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        await websocket.accept()

    client = TestClient(app)
    with (
        pytest.raises(Exception) as rejected,
        client.websocket_connect("/ws", headers={"origin": "https://attacker.example"}),
    ):
        pass
    assert getattr(rejected.value, "code", None) == 1008


@override_settings(ALLOWED_HOSTS=["testserver", "sibling.example"])
def test_websocket_origin_rejects_allowed_cross_origin_host() -> None:
    app = FastAPI()

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        await websocket.accept()

    client = TestClient(app)
    with (
        pytest.raises(Exception) as rejected,
        client.websocket_connect("/ws", headers={"origin": "https://sibling.example"}),
    ):
        pass
    assert getattr(rejected.value, "code", None) == 1008


@pytest.mark.parametrize(
    "origin",
    [
        "ftp://testserver",
        "https://testserver",
        "http://testserver:81",
        "http://testserver/path",
    ],
)
def test_websocket_origin_rejects_wrong_scheme_or_port(origin: str) -> None:
    app = FastAPI()

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        await websocket.accept()

    client = TestClient(app)
    with (
        pytest.raises(Exception) as rejected,
        client.websocket_connect("/ws", headers={"origin": origin}),
    ):
        pass
    assert getattr(rejected.value, "code", None) == 1008


def test_websocket_origin_accepts_explicit_trusted_origin() -> None:
    app = FastAPI()
    app.state.django_fastapi_config = {
        "WEBSOCKET_TRUSTED_ORIGINS": ["https://app.example"]
    }

    @app.websocket("/ws")
    async def websocket_auth(websocket: WebSocket) -> None:
        validate_websocket_origin(websocket)
        await websocket.accept()
        await websocket.close()

    client = TestClient(app)
    with client.websocket_connect("/ws", headers={"origin": "https://app.example"}):
        pass
