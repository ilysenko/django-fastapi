# Five-minute quickstart

This guide assumes an existing Django 5.2 or newer project.

## 1. Install the bridge and a server

=== "Uvicorn"

    ```bash
    python -m pip install django-fastapi uvicorn
    ```

=== "Daphne"

    ```bash
    python -m pip install django-fastapi daphne
    ```

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
