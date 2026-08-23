# Containers and Kubernetes

The repository contains runnable examples for both deployment shapes:

- `examples/asgi-only`: one ASGI service.
- `examples/split-wsgi-asgi`: WSGI and ASGI services behind Nginx.

The examples are development demonstrations. Production deployments should
build one immutable image, run as a non-root user, use a managed database and
session store, and inject secrets at runtime.

## One image, multiple roles

Build the application once and select a command per workload:

```yaml
containers:
  - name: application
    image: registry.example.com/acme/books@sha256:...
    command: ["uvicorn"]
    args: ["project.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
```

The WSGI deployment uses the same digest with a Gunicorn or uWSGI command.

## Kubernetes resources for split deployment

Create separate resources for separate scaling and health signals:

- `Deployment/books-wsgi` and `Service/books-wsgi`;
- `Deployment/books-asgi` and `Service/books-asgi`;
- one reverse-proxy or Ingress rule that routes `/api` to ASGI and `/` to WSGI;
- one migration `Job` per release;
- one `Secret` or external-secret reference shared by both deployments.

Use readiness to decide whether a pod may receive traffic. Use liveness only to
detect a process that cannot recover. A dependency outage should usually make
readiness fail without causing every pod to restart repeatedly.

## Configuration and secrets

Safe configuration belongs in ConfigMaps or environment variables. Credentials
belong in a secret manager. Never bake these into an image or commit them:

- Django `SECRET_KEY`;
- database and cache passwords;
- OAuth/JWT signing material;
- error-reporting and telemetry tokens;
- private registry credentials.

An `.env.example` may contain names and documented placeholders, never a value
copied from a real environment.

## Migrations

Do not run `manage.py migrate` in every pod entrypoint. Concurrent migration
attempts complicate rollouts and rollback. Run one explicit job before the new
application version becomes ready, and use backward-compatible migrations for
rolling deployments.
