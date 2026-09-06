# Public API

::: django_fastapi

## Database lifecycle

::: django_fastapi.database.django_db

::: django_fastapi.database.database_sync_to_async

::: django_fastapi.database.aclose_db_connections

## Authentication types

::: django_fastapi.auth.AuthResolver

::: django_fastapi.auth.AuthResolverResult

::: django_fastapi.auth.AuthUser

## WebSocket authentication

::: django_fastapi.auth.WebSocketAuth

::: django_fastapi.auth.resolve_websocket_auth

::: django_fastapi.auth.require_websocket_user

::: django_fastapi.auth.validate_websocket_origin

## ASGI composition

`mount_django_fastapi_app` and `get_django_fastapi_application` accept
`websocket_app`, `websocket_path`, `lifespan`, and `root_routes` keyword arguments.
`root_routes` is a sequence of Starlette routes placed before the exact WebSocket
route, HTTP mount, and Django fallback. Use it for project-owned root endpoints.
The root and HTTP lifespan states are merged, with root values taking precedence.
WebSocket-app lifespan hooks are not entered separately; shared resources belong
in the root lifespan. See [WebSockets](websockets.md#root-lifespan).
