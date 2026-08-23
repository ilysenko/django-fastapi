# Split WSGI and ASGI example

This example keeps ordinary Django traffic on Gunicorn/WSGI and sends `/api`
to a separate Uvicorn/ASGI service. Both services use the same image, settings,
PostgreSQL database, and database-backed Django sessions.

From the repository root:

```bash
docker compose -f examples/split-wsgi-asgi/compose.yaml up --build
```

If port 8080 is occupied, set `EXAMPLE_HTTP_PORT`, for example
`EXAMPLE_HTTP_PORT=18080`, and use that port in the commands below.

Verify both paths:

```bash
curl http://localhost:8080/django-health/
curl http://localhost:8080/api/health
```

Then verify that a session created by Django/WSGI authenticates the same user
through FastAPI/ASGI:

```bash
python scripts/smoke_example.py
```

The local-only credentials are `reader` / `local-example-password`.

The Compose database deliberately uses trust authentication on its private
development network. Do not use that setting outside this local example.

`kubernetes.yaml` is a deployment template showing separate Deployments,
Services, health probes, a one-shot migration Job, and prefix routing. Create
the referenced runtime Secret through your secret manager before adapting it.
