# WebSockets

WebSocket routers are deliberately separate from HTTP routers. Django's CSRF
middleware protects unsafe HTTP requests, while a WebSocket handshake is
protected by strict Host and Origin validation.

## Configure and mount one WebSocket endpoint

```python
# project/realtime.py
from fastapi import APIRouter, WebSocket
from django_fastapi import resolve_websocket_auth, validate_websocket_origin

router = APIRouter()


@router.websocket("/")
async def realtime(websocket: WebSocket):
    validate_websocket_origin(websocket)
    auth = await resolve_websocket_auth(websocket)
    await websocket.accept()
    await websocket.send_json({"authenticated": auth.user.is_authenticated})
```

```python
# settings.py
DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "ROUTERS": ["project.api.router"],
    "WEBSOCKET_ROUTERS": ["project.realtime.router"],
}
```

```python
# asgi.py
from django.core.asgi import get_asgi_application
from django_fastapi import (
    create_fastapi_app,
    create_websocket_app,
    mount_django_fastapi_app,
)

application = mount_django_fastapi_app(
    get_asgi_application(),
    create_fastapi_app(),
    websocket_app=create_websocket_app(),
    websocket_path="/ws",
)
```

Only the exact `/ws` path reaches the WebSocket app. Other WebSocket paths are
closed with code 1008 instead of falling through to Django.

## Authentication and anonymous sessions

`resolve_websocket_auth()` loads the configured Django session cookie and
returns `WebSocketAuth`, containing the Django request, session, session key,
and current user. A missing session cookie is valid and produces an anonymous
user with no session key. Use `require_websocket_user()` when anonymous
connections are not allowed.

If an anonymous workflow needs a stable session audience, create and persist
the Django session in the preceding HTTP response. A WebSocket handshake cannot
reliably create a browser cookie after it has upgraded.

## Origin security

Call `validate_websocket_origin()` before `accept()`. It validates `Host`
against Django's `ALLOWED_HOSTS` and requires `Origin` to match the effective
HTTP/HTTPS scheme, hostname, and port corresponding to the WS/WSS connection;
missing or untrusted values close with code 1008. This prevents another website
from using a victim's ambient session cookie to open your socket.

For an intentional cross-origin frontend, list complete origins explicitly in
`DJANGO_FASTAPI["WEBSOCKET_TRUSTED_ORIGINS"]`, for example
`["https://app.example.com"]`. Merely listing two sibling domains in
`ALLOWED_HOSTS` does not permit them to open each other's WebSockets.

CSRF tokens do not protect WebSocket messages. Keep HTTP CSRF enabled for
cookie-authenticated HTTP routes and use Origin validation for WebSockets.

## Proxy headers and heartbeat

Forward the original `Host`, scheme, and client address only through trusted
proxies. Configure Uvicorn's `--forwarded-allow-ips` to the actual proxy
boundary. Forward `Upgrade` and `Connection` only on the intended WebSocket
location and disable proxy buffering there.

Protocol ping/pong is server configuration, not application routing. An
application-level ping is still useful for detecting a half-open browser path
and should carry an unpredictable nonce that the server echoes.

## Root lifespan

Pass an async context manager through `lifespan=` when the root application
owns shared resources. The composer enters the supplied root lifespan and the
HTTP FastAPI lifespan once each. If a later startup step fails, already-entered
contexts are exited in reverse order. Mappings yielded by both contexts are
merged into `request.state`; values from the supplied root lifespan take
precedence when both mappings contain the same key.

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    await shared_hub.start()
    try:
        yield {"shared_hub": shared_hub}
    finally:
        await shared_hub.close()
```

The WebSocket application's own lifespan is not entered separately. Use
`database_sync_to_async` for each short ORM operation and finish transactions
before waiting for messages. HTTP `AUTH_RESOLVERS` and `SESSION_MIDDLEWARE` hooks
do not change `resolve_websocket_auth()`, which uses Django's standard session
middleware and authentication. Applications with additional account policy must
check it explicitly before accepting the connection.
