# Configuration reference

Set `DJANGO_FASTAPI` in Django settings. All entries are optional.

```python
DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "TITLE": "Django FastAPI",
    "FASTAPI_KWARGS": {},
    "ROUTERS": [],
    "APP_CONFIGURATORS": [],
    "AUTH_RESOLVERS": ["django_fastapi.auth.session_auth_resolver"],
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
| `APP_CONFIGURATORS` | `[]` | Dotted paths to callables receiving the created FastAPI app. |
| `AUTH_RESOLVERS` | session resolver | Ordered sync or async user resolvers. |
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
provided here.
