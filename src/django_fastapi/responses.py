from __future__ import annotations

from typing import Any, cast

from anyio import CancelScope
from django.http import HttpResponse, HttpResponseBase, StreamingHttpResponse
from starlette.responses import Response, StreamingResponse
from starlette.types import Send


class _DjangoStreamingResponse(StreamingResponse):
    """Close Django's async source in the task that advanced it."""

    def __init__(self, response: StreamingHttpResponse, **kwargs: Any) -> None:
        # streaming_content is a Django wrapper: closing it does not propagate
        # aclose() to the original iterator suspended at its last yield.
        self._source = cast(Any, response)._iterator if response.is_async else None
        super().__init__(response.streaming_content, **kwargs)

    async def stream_response(self, send: Send) -> None:
        try:
            await super().stream_response(send)
        finally:
            if self._source is not None:
                # ASGI <2.4 streams in a child task. Cleanup in __call__ or in
                # a new shielded task would invalidate generator ContextVar tokens.
                with CancelScope(shield=True):
                    try:
                        close_source = getattr(self._source, "aclose", None)
                        if close_source is not None:
                            await close_source()
                    finally:
                        close_wrapper = getattr(self.body_iterator, "aclose", None)
                        if close_wrapper is not None:
                            await close_wrapper()


def django_response_to_fastapi(response: HttpResponseBase) -> Response:
    """Convert a Django response into a Starlette response."""
    headers = {
        key: value
        for key, value in response.items()
        if key.lower() not in {"content-type", "set-cookie"}
    }
    content_type = response.get("Content-Type", None)
    if isinstance(response, StreamingHttpResponse):
        fastapi_response: Response = _DjangoStreamingResponse(
            response,
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
