# Architecture

Modern Django exposes both WSGI and ASGI entrypoints. FastAPI is ASGI-only.
This bridge composes a FastAPI application and Django's ASGI application under
one outer Starlette router.

```text
                    ┌──────────────────────────┐
HTTP request ──────▶│ combined ASGI application│
                    └────────────┬─────────────┘
                                 │
                    ┌────────────┴─────────────┐
                    │                          │
             matches PREFIX              no prefix match
                    │                          │
                    ▼                          ▼
                FastAPI                   Django ASGI
```

Django must be initialized before application routers import Django models.
`get_django_fastapi_application()` calls Django's normal
`get_asgi_application()` first and then creates and mounts FastAPI.

## Shared process state

When both applications run in one ASGI process they naturally share:

- `DJANGO_SETTINGS_MODULE` and Django settings;
- database connections and model definitions;
- cache and session configuration;
- authentication backends;
- environment variables and logging configuration.

When WSGI and ASGI run as separate services, they still share those logical
resources, but each service has its own processes and connection pools. See
[the WSGI deployment guide](deployment/wsgi.md).

## Request adaptation

`get_django_request` builds a Django `ASGIRequest` from the FastAPI request,
attaches Django's session, resolves a user, and caches the result on
`request.state`. This is an adapter, not a pass through Django's configured
middleware chain.

The default authentication resolver runs Django's `AuthenticationMiddleware`.
Unsafe methods also run Django's `CsrfViewMiddleware` unless exempted.

## Sync and async are endpoint decisions

The server protocol does not make every function asynchronous:

- FastAPI runs `def` operations in a worker thread. Normal synchronous Django
  ORM calls are appropriate there.
- FastAPI runs `async def` operations in the event loop. Use Django's async ORM
  methods or cross to one synchronous service with `sync_to_async`.
