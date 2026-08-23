# Troubleshooting

## FastAPI returns 404 behind Nginx

Confirm that the external path still includes the configured `PREFIX` when it
reaches the ASGI server. An Nginx `proxy_pass` URI suffix can strip `/api`.

## Django session works on the website but not the API

Compare the WSGI and ASGI settings and environment:

- session backend and endpoint;
- `SECRET_KEY`;
- cookie name, domain, path, Secure, and SameSite;
- deployed application version;
- request host and scheme.

Local-memory sessions cannot be shared between processes or replicas.

## CSRF fails only in production

Check the forwarded scheme, trusted origins, cookie domain/path, secure-cookie
settings, and whether the client sends both the cookie and `X-CSRFToken`.
Inspect names and status codes, never log token values.

## `SynchronousOnlyOperation`

A synchronous Django API was called in an event-loop thread. Use the async ORM,
change the FastAPI operation to `def`, or move the complete synchronous workflow
into one `sync_to_async(thread_sensitive=True)` call.

Do not use `DJANGO_ALLOW_ASYNC_UNSAFE` as a production fix.

## Streaming arrives all at once

Disable proxy buffering for the specific SSE or streaming location and extend
its read timeout. Leave buffering enabled for ordinary JSON endpoints.

## Database connections are exhausted after adding ASGI

Count pools across both WSGI and ASGI replicas, workers, background jobs, and
deploy overlap. Reduce worker/pool sizes or introduce a correctly sized backend
pooler before increasing database limits blindly.

## OpenAPI has the wrong URL prefix

Preserve the mount path at the proxy and configure forwarded headers/root path
consistently. Test `/api/openapi.json` through the public load balancer, not only
against a container port.
