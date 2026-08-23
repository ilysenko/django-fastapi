# Django and FastAPI, in one project

`django-fastapi` lets an existing Django project serve FastAPI routes without
giving up Django's settings, models, migrations, sessions, users, or admin.

It is intentionally small. The bridge creates a FastAPI application, wires in
Django-aware request and security dependencies, and mounts FastAPI beside the
Django ASGI application.

```text
ASGI request
└── combined application
    ├── configured API prefix → FastAPI
    └── everything else      → Django ASGI
```

## When it is useful

- You want FastAPI request validation and OpenAPI in an established Django
  project.
- New endpoints should use the existing Django user and session cookie.
- New code should query existing Django models directly.
- A large WSGI deployment needs a gradual, separately scalable ASGI path.

## What it does not do

- It does not register FastAPI in Django's `urls.py`.
- It does not run the complete Django middleware stack for FastAPI routes.
- It does not turn synchronous ORM calls into asynchronous calls.
- It does not generate Pydantic schemas from Django models.
- It does not choose or bundle a production ASGI server.

[Start with the five-minute guide](quickstart.md){ .md-button .md-button--primary }
[Plan a production deployment](deployment/index.md){ .md-button }
