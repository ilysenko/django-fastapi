# ASGI-only example

This example runs Django and FastAPI through one Uvicorn service, with Nginx in
front. It is intentionally small and uses PostgreSQL plus a development-only
secret.

From the repository root:

```bash
docker compose -f examples/asgi-only/compose.yaml up --build
```

If port 8080 is occupied, set `EXAMPLE_HTTP_PORT`, for example
`EXAMPLE_HTTP_PORT=18080`, and use that port in the URLs below.

Then open:

- `http://localhost:8080/api/health`
- `http://localhost:8080/api/docs`
- `http://localhost:8080/django-health/`

The migration job also creates a local `reader` user and one book. Verify that
the Django login session is visible to FastAPI:

```bash
python scripts/smoke_example.py
```

The local-only credentials are `reader` / `local-example-password`. The
Compose database deliberately uses trust authentication on its private
development network. Neither setting is suitable for production.

This is a topology example, not a hardened production image. Read the
production security and operations guides before adapting it.
