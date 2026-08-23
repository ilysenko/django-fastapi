# Deploy when Django already uses ASGI

Run the combined application as the project's only HTTP entrypoint:

```bash
uvicorn project.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers \
  --forwarded-allow-ips="10.0.0.0/8"
```

Replace the trusted proxy range with the real network boundary. Never trust
forwarded headers from every internet client.

Nginx only needs one upstream:

```nginx
upstream application_asgi {
    server app:8000;
}

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://application_asgi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Synchronous Django code is allowed

ASGI does not require every Django view or FastAPI operation to be rewritten.
Django adapts synchronous views, and FastAPI runs `def` operations in a worker
thread.

The important boundary is inside `async def`: do not call blocking ORM or
third-party synchronous code directly in the event loop.

## Worker and thread sizing

- More ASGI workers increase CPU parallelism and create more independent event
  loops and database pools.
- Synchronous FastAPI operations use Starlette's thread limiter.
- Synchronous Django middleware and views may also occupy threads.
- Long-lived SSE or long-polling requests consume in-flight capacity even when
  they are not CPU-heavy.

Load-test a representative mix of sync ORM, async I/O, and long-lived requests.
Do not choose worker counts from CPU count alone.

## Disconnects and shutdown

Long-lived handlers should allow cancellation to propagate and clean up in a
`finally` block. Set the orchestrator termination grace period longer than the
server's graceful-shutdown timeout, and stop accepting new traffic before the
process exits.
