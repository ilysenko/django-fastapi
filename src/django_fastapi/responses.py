from __future__ import annotations

from django.http import HttpResponse, HttpResponseBase, StreamingHttpResponse
from starlette.responses import Response, StreamingResponse


def django_response_to_fastapi(response: HttpResponseBase) -> Response:
    """Convert a Django response into a Starlette response."""
    headers = {
        key: value
        for key, value in response.items()
        if key.lower() not in {"content-type", "set-cookie"}
    }
    content_type = response.get("Content-Type", None)
    if isinstance(response, StreamingHttpResponse):
        fastapi_response: Response = StreamingResponse(
            response.streaming_content,
            status_code=response.status_code,
            headers=headers,
            media_type=content_type,
        )
    else:
        http_response = response
        assert isinstance(http_response, HttpResponse)
        fastapi_response = Response(
            content=http_response.content,
            status_code=response.status_code,
            headers=headers,
            media_type=content_type,
        )

    for morsel in response.cookies.values():
        fastapi_response.headers.append("set-cookie", morsel.OutputString())
    return fastapi_response


__all__ = ["django_response_to_fastapi"]
