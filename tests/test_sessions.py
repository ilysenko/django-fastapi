from __future__ import annotations

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ImproperlyConfigured
from fastapi import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from django_fastapi import create_fastapi_app, get_django_request


class AsyncSessionMiddleware(SessionMiddleware):
    events: list[str] = []

    async def aprocess_request(self, request):
        self.events.append("request")
        request.session["prepared"] = True

    async def aprocess_response(self, request, response):
        self.events.append("response")
        return super().process_response(request, response)


class InvalidAsyncHook(SessionMiddleware):
    def aprocess_request(self, request):
        pass


class MissingRequestHook:
    def process_response(self, request, response):
        return response


class MissingResponseHook:
    def process_request(self, request):
        pass


class FailingRequestHook(AsyncSessionMiddleware):
    async def aprocess_request(self, request):
        raise RuntimeError("session read failed")


class FailingResponseHook(AsyncSessionMiddleware):
    async def aprocess_response(self, request, response):
        raise RuntimeError("session write failed")


@pytest.mark.parametrize("status", [200, 204, 304])
@pytest.mark.parametrize("async_hooks", [False, True])
def test_session_hooks_preserve_raw_response_headers(settings, status, async_hooks):
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    AsyncSessionMiddleware.events = []
    config = {"AUTH_RESOLVERS": []}
    if async_hooks:
        config["SESSION_MIDDLEWARE"] = f"{__name__}.AsyncSessionMiddleware"
    app = create_fastapi_app(config)

    @app.get("/")
    async def endpoint(request: Request):
        adapted = await get_django_request(request)
        if async_hooks:
            assert adapted.session["prepared"]
            assert AsyncSessionMiddleware.events == ["request"]
        adapted.session["saved"] = True
        response = Response(status_code=status, headers={"Vary": "Accept-Encoding"})
        response.set_cookie("first", "one")
        response.set_cookie("second", "two")
        return response

    response = TestClient(app).get("/")
    assert response.status_code == status
    assert "content-type" not in response.headers
    assert set(response.headers["vary"].lower().split(", ")) == {
        "accept-encoding",
        "cookie",
    }
    assert len(response.headers.get_list("set-cookie")) == 3
    assert response.cookies["first"] == "one"
    assert response.cookies["second"] == "two"
    assert settings.SESSION_COOKIE_NAME in response.cookies
    if async_hooks:
        assert AsyncSessionMiddleware.events == ["request", "response"]


@pytest.mark.parametrize(
    "path",
    [
        "",
        123,
        "nonexistent_session_module.Middleware",
        f"{__name__}.InvalidAsyncHook",
        f"{__name__}.MissingRequestHook",
        f"{__name__}.MissingResponseHook",
    ],
)
def test_invalid_session_middleware_fails_at_startup(path):
    with pytest.raises(ImproperlyConfigured, match="SESSION_MIDDLEWARE"):
        create_fastapi_app({"SESSION_MIDDLEWARE": path})


@pytest.mark.parametrize(
    "middleware,error",
    [
        (FailingRequestHook, "session read failed"),
        (FailingResponseHook, "session write failed"),
    ],
)
def test_session_backend_failure_is_not_an_anonymous_success(
    settings, middleware, error
):
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    app = create_fastapi_app(
        {
            "AUTH_RESOLVERS": [],
            "SESSION_MIDDLEWARE": f"{__name__}.{middleware.__name__}",
        }
    )

    @app.get("/")
    async def endpoint(request: Request):
        await get_django_request(request)
        return {"ok": True}

    with pytest.raises(RuntimeError, match=error):
        TestClient(app).get("/")
