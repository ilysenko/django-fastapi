# django-fastapi

[![CI](https://github.com/ilysenko/django-fastapi/actions/workflows/ci.yml/badge.svg)](https://github.com/ilysenko/django-fastapi/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://ilysenko.github.io/django-fastapi/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Run FastAPI beside an existing Django application while keeping Django in
charge of settings, models, migrations, sessions, and users.

`django-fastapi` is an ASGI bridge. It does not add FastAPI routes to Django's
`urls.py`, replace Django middleware, or generate API schemas from Django
models. It creates a FastAPI application and mounts it before Django's ASGI
fallback.

```text
ASGI server
└── combined application
    ├── /api/* → FastAPI
    └── /*      → Django ASGI
```

## Installation

For ORM routes, see [connection ownership](docs/orm.md#connection-ownership):
decorate synchronous ORM handlers/dependencies with `@django_db`, use
`database_sync_to_async` for short synchronous DB units from async code, and
release connections before long external waits. HTTP requests receive automatic
thread-sensitive cleanup; WebSocket operations need explicit short DB boundaries.

The current documentation describes the **unreleased 0.2.0 source snapshot**.
Install a reviewed public commit to use the WebSocket and database lifecycle APIs:

```bash
git clone https://github.com/ilysenko/django-fastapi.git
cd django-fastapi
# Record this public commit and use it for repeatable installations.
DJANGO_FASTAPI_COMMIT=$(git rev-parse HEAD)
python -m pip install "django-fastapi @ git+https://github.com/ilysenko/django-fastapi.git@${DJANGO_FASTAPI_COMMIT}"
python -m pip install uvicorn  # or daphne
```

Publishing source and documentation does not publish a new package to PyPI.


## Five-minute setup

Create a router in any Django app:

```python
# books/api.py
from fastapi import APIRouter

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Configure the bridge in Django settings:

```python
DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "TITLE": "Example API",
    "ROUTERS": ["books.api.router"],
}
```

Mount it in the project's ASGI entrypoint:

```python
# project/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

from django_fastapi import get_django_fastapi_application

application = get_django_fastapi_application()
```

Run the combined application:

```bash
uvicorn project.asgi:application
```

FastAPI is now available at `/api`, including OpenAPI at `/api/docs`. Existing
Django URLs continue to use the Django ASGI application.

## Django user and session access

The default resolver uses Django's normal session cookie:

```python
from typing import Annotated, Any

from fastapi import Depends
from django_fastapi import get_authenticated_user


@router.get("/me")
def me(
    user: Annotated[Any, Depends(get_authenticated_user)],
) -> dict[str, str]:
    return {"username": user.get_username()}
```

CSRF protection is enabled by default for unsafe methods. Custom JWT, OAuth,
or API-key authentication can be added with an auth resolver without changing
the bridge.

## Existing WSGI deployments

FastAPI requires an ASGI server, but an existing synchronous Django deployment
does not need to be migrated all at once. Run one WSGI service for existing
Django URLs and a second ASGI service for the FastAPI prefix, then route both
through the same reverse proxy:

```text
Nginx
├── /api/* → ASGI service → FastAPI + Django ASGI
└── /*      → WSGI service → Django WSGI
```

Both services must run the same code and share Django settings, database,
session store, cookie settings, and secrets. See the
[deployment guide](https://ilysenko.github.io/django-fastapi/deployment/) for
complete Nginx, Docker Compose, and Kubernetes examples.

## Documentation

- [Architecture and quickstart](https://ilysenko.github.io/django-fastapi/quickstart/)
- [Authentication, sessions, and CSRF](https://ilysenko.github.io/django-fastapi/authentication/)
- [Pydantic and Django models](https://ilysenko.github.io/django-fastapi/pydantic/)
- [WebSockets](https://ilysenko.github.io/django-fastapi/websockets/)
- [Sync and async ORM usage](https://ilysenko.github.io/django-fastapi/orm/)
- [Production deployment](https://ilysenko.github.io/django-fastapi/deployment/)
- [Configuration reference](https://ilysenko.github.io/django-fastapi/configuration/)

## Development

```bash
python -m pip install -e ".[test,lint,docs,release]"
pytest
ruff check .
ruff format --check .
mypy
mkdocs build --strict
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

MIT

## API discovery settings

The bridge preserves FastAPI's default `/docs`, `/redoc`, and `/openapi.json`
endpoints. The bundled deployment examples disable all three explicitly with
`FASTAPI_KWARGS`; remove that override to enable them for local exploration.
Use the same options on HTTP and WebSocket apps when discovery should be disabled.
