# Add FastAPI beside an existing WSGI deployment

This is the gradual-migration topology. Existing Django traffic remains on its
current synchronous server. Only the selected API prefix reaches ASGI.

```text
                         ┌─▶ WSGI replicas ─▶ project.wsgi:application
client ─▶ Nginx ─────────┤
                         └─▶ ASGI replicas ─▶ project.asgi:application
```

## Run two commands from one image

```bash
# Existing Django service
gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Equivalent WSGI option
uwsgi --http 0.0.0.0:8000 --module project.wsgi:application --master --processes 4

# New FastAPI/ASGI service
uvicorn project.asgi:application --host 0.0.0.0 --port 8001 --workers 2
```

Daphne is an equivalent ASGI option:

```bash
daphne -b 0.0.0.0 -p 8001 project.asgi:application
```

Use the same image digest and settings for both commands.

## Nginx routing

```nginx
upstream django_wsgi {
    server wsgi:8000;
}

upstream django_asgi {
    server asgi:8001;
}

server {
    listen 80;
    server_name example.com;

    location = /api {
        # Preserve the exact mount path too; do not send it to WSGI.
        proxy_pass http://django_asgi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        # No URI suffix here: preserve /api/... for the ASGI mount.
        proxy_pass http://django_asgi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://django_wsgi;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The trailing-slash rules of `proxy_pass` can strip or rewrite the prefix. Test
the exact external `/api/...` path in deployment smoke tests.

## Shared state checklist

Both services need identical:

- `SECRET_KEY` and signing configuration;
- database and cache endpoints;
- a shared database or Redis/cache session engine (never process-local memory);
- `SESSION_COOKIE_NAME`, `SESSION_COOKIE_DOMAIN`, `SESSION_COOKIE_PATH`,
  `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and
  `SESSION_COOKIE_SAMESITE`;
- authentication backends;
- `ALLOWED_HOSTS`, CSRF trusted origins, and timezone;
- application version and migrations.

Do not use local-memory sessions or local-memory cache across replicas. A
request may authenticate through WSGI and then reach any ASGI replica.

## Capacity planning

WSGI and ASGI services create separate database pools. Calculate the upper
bound before scaling:

```text
total connections ≈
    WSGI replicas × WSGI workers × connections per worker
  + ASGI replicas × ASGI workers × connections per worker
  + background jobs and migration headroom
```

Scale the API independently, but keep the database budget as a shared limit.

## Release process

1. Build one immutable image.
2. Run database migrations once in a dedicated job.
3. Roll out WSGI and ASGI services from that image.
4. Wait for readiness before removing old replicas.
5. Verify session continuity across both paths.
6. Roll back both services together if the application contract changed.
