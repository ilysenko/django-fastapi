# Testing

Use Starlette's `TestClient` against the combined ASGI application. Django's
test database and pytest-django continue to work.

```python
from starlette.testclient import TestClient
from project.asgi import application


def test_health():
    response = TestClient(application).get("/api/health")
    assert response.status_code == 200
```

## Authenticated client

Create a session with Django's client and copy the cookie:

```python
from django.conf import settings
from django.test import Client as DjangoClient
from starlette.testclient import TestClient


def asgi_client_for(user):
    django_client = DjangoClient()
    django_client.force_login(user)

    client = TestClient(application)
    cookie = django_client.cookies[settings.SESSION_COOKIE_NAME]
    client.cookies.set(settings.SESSION_COOKIE_NAME, cookie.value)
    return client
```

## What to test

- Anonymous, authenticated, and staff dependencies.
- Valid and invalid CSRF submissions.
- The actual session backend used in production.
- Custom resolver precedence and token failures.
- Pydantic rejection of unknown or malformed input.
- Permission-aware response fields.
- Query counts for response mappers and related objects.
- Both synchronous and asynchronous ORM paths.
- The combined mount prefix and Django fallback.

Do not replace application-level tests with OpenAPI snapshots. OpenAPI proves
the declared contract, not authorization or database behavior.
