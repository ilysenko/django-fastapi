from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from fastapi import FastAPI
from starlette.requests import ClientDisconnect
from starlette.responses import Response
from starlette.testclient import TestClient

from django_fastapi import create_fastapi_app, django_response_to_fastapi


def test_django_response_to_fastapi_converts_plain_response() -> None:
    django_response = HttpResponse(
        b"created",
        content_type="text/plain",
        status=201,
    )
    django_response["X-Test"] = "yes"

    response = django_response_to_fastapi(django_response)

    assert response.status_code == 201
    assert response.body == b"created"
    assert response.media_type == "text/plain"
    assert response.headers["x-test"] == "yes"


def test_django_response_to_fastapi_preserves_json_content_type() -> None:
    response = django_response_to_fastapi(JsonResponse({"ok": True}))

    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert response.body == b'{"ok": true}'


def test_django_response_to_fastapi_preserves_cookies() -> None:
    django_response = HttpResponse("ok")
    django_response.set_cookie("sessionid", "abc")

    response = django_response_to_fastapi(django_response)

    assert "sessionid=abc" in response.headers["set-cookie"]


def test_django_response_to_fastapi_converts_streaming_response() -> None:
    app = FastAPI()

    @app.get("/")
    def stream() -> Response:
        return django_response_to_fastapi(
            StreamingHttpResponse(
                iter([b"stream", b"ed"]),
                content_type="text/plain",
                status=202,
            )
        )

    response = TestClient(app).get("/")

    assert response.status_code == 202
    assert response.text == "streamed"
    assert response.headers["content-type"].startswith("text/plain")


def test_django_exceptions_are_translated_to_json_responses() -> None:
    app = create_fastapi_app({})

    @app.get("/missing")
    def missing() -> None:
        raise Http404("Book not found.")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise PermissionDenied("Book is private.")

    client = TestClient(app)

    assert client.get("/missing").json() == {"detail": "Book not found."}
    assert client.get("/missing").status_code == 404
    assert client.get("/forbidden").json() == {"detail": "Book is private."}
    assert client.get("/forbidden").status_code == 403


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
@pytest.mark.parametrize("failure", ["send", "disconnect", "complete"])
def test_async_stream_closes_source_in_consuming_task(spec_version, failure):
    import asyncio
    from contextvars import ContextVar

    owner = ContextVar("stream_owner")
    finalized = []

    async def run():
        sent = asyncio.Event()

        async def source():
            task = asyncio.current_task()
            token = owner.set(task)
            try:
                yield b"first"
                if failure == "disconnect":
                    await asyncio.sleep(60)
                yield b"second"
            finally:
                await asyncio.sleep(0)
                assert asyncio.current_task() is task
                owner.reset(token)
                finalized.append(True)

        response = django_response_to_fastapi(StreamingHttpResponse(source()))

        async def receive():
            await sent.wait()
            if failure == "disconnect":
                return {"type": "http.disconnect"}
            await asyncio.sleep(60)

        async def send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                sent.set()
                if failure == "send":
                    raise OSError("client disconnected")
                if failure == "disconnect" and spec_version == "2.4":
                    # New ASGI servers report disconnects as send errors.
                    raise OSError("client disconnected")
                if failure == "disconnect":
                    # Disconnect while sending a yielded chunk: the adapter
                    # must close the suspended source under its cleanup shield.
                    await asyncio.sleep(60)

        try:
            await response(
                {"type": "http", "asgi": {"spec_version": spec_version}}, receive, send
            )
        except Exception as exc:
            assert failure in {"send", "disconnect"}
            errors = getattr(exc, "exceptions", (exc,))
            assert all(
                isinstance(error, (OSError, ClientDisconnect)) for error in errors
            )
        assert finalized == [True]

    asyncio.run(run())
