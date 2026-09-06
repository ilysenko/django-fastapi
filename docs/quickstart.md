# Five-minute quickstart

This guide assumes an existing Django 5.2 or newer project.

## 1. Install the bridge and a server

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


## 2. Add a FastAPI router

```python
# books/api.py
from fastapi import APIRouter

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

The router belongs to the Django app, but it is not added to `urlpatterns`.

## 3. Configure FastAPI

```python
# project/settings.py
DJANGO_FASTAPI = {
    "PREFIX": "/api",
    "TITLE": "Example API",
    "ROUTERS": ["books.api.router"],
}
```

## 4. Create the combined ASGI entrypoint

```python
# project/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

from django_fastapi import get_django_fastapi_application

application = get_django_fastapi_application()
```

Keep imports that load Django models after `DJANGO_SETTINGS_MODULE` is set.

## 5. Run it

=== "Uvicorn"

    ```bash
    uvicorn project.asgi:application --host 127.0.0.1 --port 8000
    ```

=== "Daphne"

    ```bash
    daphne -b 127.0.0.1 -p 8000 project.asgi:application
    ```

Open these URLs:

- `http://127.0.0.1:8000/api/books/health`
- `http://127.0.0.1:8000/api/docs`
- any existing Django URL at its original path

## 6. Read the Django user

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

A browser logged in through Django sends the same session cookie to `/api`.
The default resolver returns the same Django user.

Next, read [authentication and CSRF](authentication.md) and choose the correct
[ORM calling style](orm.md).

## API discovery settings

The bridge preserves FastAPI's default `/docs`, `/redoc`, and `/openapi.json`
endpoints. The bundled deployment examples disable all three explicitly with
`FASTAPI_KWARGS`; remove that override to enable them for local exploration.
Use the same options on HTTP and WebSocket apps when discovery should be disabled.
