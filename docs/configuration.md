# Configuration reference

Set `DJANGO_FASTAPI` in Django settings. All entries are optional.

```python
DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "TITLE": "Django FastAPI",
    "FASTAPI_KWARGS": {},
    "ROUTERS": [],
    "WEBSOCKET_ROUTERS": [],
    "WEBSOCKET_TRUSTED_ORIGINS": [],
    "APP_CONFIGURATORS": [],
    "AUTH_RESOLVERS": ["django_fastapi.auth.session_auth_resolver"],
    # Optional: omit to use Django's SessionMiddleware.
    "SESSION_MIDDLEWARE": "django.contrib.sessions.middleware.SessionMiddleware",
    "CSRF": {
        "ENABLED": True,
        "EXEMPT_PATHS": [],
    },
}
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `PREFIX` | `"/api"` | Outer ASGI mount path. A leading slash is added and a trailing slash removed. |
| `TITLE` | `"Django FastAPI"` | FastAPI title unless supplied in `FASTAPI_KWARGS`. |
| `FASTAPI_KWARGS` | `{}` | Keyword arguments passed to `FastAPI(...)`. |
| `ROUTERS` | `[]` | Dotted paths to `fastapi.APIRouter` objects, included in order. |
| `WEBSOCKET_ROUTERS` | `[]` | Routers included on the separate WebSocket app. |
| `WEBSOCKET_TRUSTED_ORIGINS` | `[]` | Explicit complete origins allowed to bypass same-origin WebSocket validation. |
| `APP_CONFIGURATORS` | `[]` | Dotted paths to callables receiving the created FastAPI app. |
| `AUTH_RESOLVERS` | session resolver | Ordered sync or async user resolvers. |
| `SESSION_MIDDLEWARE` | Django `SessionMiddleware` | Optional HTTP session middleware class; supports async request/response hooks. See [session hooks](authentication.md#custom-http-session-hooks). |
| `CSRF.ENABLED` | `True` | Require Django CSRF validation for unsafe methods. |
| `CSRF.EXEMPT_PATHS` | `[]` | Exact paths exempted from CSRF validation. |

Invalid mappings, path lists, router objects, configurators, and auth resolvers
raise `django.core.exceptions.ImproperlyConfigured` during application startup.

## Routers

Each dotted path must resolve to an `APIRouter` instance:

```python
"ROUTERS": [
    "users.api.router",
    "billing.api.router",
]
```

Order matters when routes overlap.

## App configurators

Use a configurator for FastAPI-level setup that cannot live on a router:

```python
from fastapi import FastAPI


def configure_api(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
```

```python
"APP_CONFIGURATORS": ["project.api.configure_api"]
```

Configurators run before configured routers are included.

## FastAPI keyword arguments

```python
"FASTAPI_KWARGS": {
    "docs_url": None,
    "redoc_url": None,
    "openapi_url": None,
}
```

The bridge appends its CSRF dependency to any global dependencies already
provided here. The separate WebSocket app receives the same keyword arguments
except `dependencies`, which are removed, and its generated WebSocket title.
HTTP auth resolvers, session hooks, and app configurators are HTTP-only.

## WebSocket routers

`WEBSOCKET_ROUTERS` contains dotted paths to `fastapi.APIRouter` objects, just
like `ROUTERS`, but they are installed on a separate application without the
HTTP CSRF dependency:

```python
DJANGO_FASTAPI = {
    "PREFIX": "/async/api",
    "ROUTERS": ["project.http.router"],
    "WEBSOCKET_ROUTERS": ["project.realtime.router"],
}
```

Create and mount that application explicitly with `create_websocket_app()` and
the `websocket_app=` argument to `mount_django_fastapi_app()`.
