from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from fastapi import FastAPI
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
