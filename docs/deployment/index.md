# Deployment overview

FastAPI requires ASGI. The right topology depends on how Django is deployed
today.

## Django already uses ASGI

Run one combined application:

```text
Load balancer / Nginx
└── ASGI service
    ├── /api/* → FastAPI
    └── /*      → Django ASGI
```

[Read the ASGI deployment guide](asgi.md).

## Django currently uses WSGI

Keep the existing WSGI service and add an independently scalable ASGI service:

```text
Load balancer / Nginx
├── /api/* → ASGI service → FastAPI + Django ASGI
└── /*      → WSGI service → Django WSGI
```

[Read the WSGI deployment guide](wsgi.md).

## Invariants for both topologies

- Deploy exactly the same application version to every process.
- Run migrations once as a release job, not in every web container.
- Keep secrets in a secret manager, never an image or repository.
- Send correct proxy headers and trust only known proxy addresses.
- Size the total database pool across every worker and replica.
- Use a shared production session backend.
- Test graceful termination under real request duration.

The examples use Uvicorn and Gunicorn for portability. Daphne, uWSGI, or
another conforming server can be substituted without changing the bridge.
