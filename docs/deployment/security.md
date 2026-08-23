# Production security

## HTTPS and proxy trust

Terminate HTTPS at a controlled proxy and pass the original scheme and host.
Configure Django to trust only that proxy. Do not accept arbitrary forwarded
headers from the internet.

Set production values for `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, secure
cookies, HSTS, and your proxy SSL-header setting.

## Authentication and CSRF

Cookie-authenticated APIs must keep CSRF enabled. A webhook exemption is safe
only when the handler verifies a strong provider signature, timestamp, and
replay policy.

Custom token resolvers must validate signature, algorithm, issuer, audience,
expiry, revocation, and required scopes before returning a user.

## OpenAPI endpoints

Interactive API documentation can disclose routes and request shapes. Disable
it in settings when it is not intended for production users:

```python
"FASTAPI_KWARGS": {
    "docs_url": None,
    "redoc_url": None,
    "openapi_url": None,
}
```

Alternatively, protect documentation at the proxy with a separate access
policy. Do not assume application session auth automatically protects it.

## CORS is separate from CSRF

CORS decides which browser origins may read cross-origin responses. CSRF
protects state-changing cookie-authenticated requests. Configure both when a
separate frontend origin calls the API; enabling one does not replace the
other.

## Limits

Enforce request-body, header, connection, and timeout limits at the edge. Keep
application validation as a second boundary. Rate-limit login, token, upload,
and expensive endpoints according to their actual abuse risk.

## Secrets

Use runtime secret injection and least-privilege service identities. Rotate
secrets through a planned overlap period. Keep production values out of source,
container layers, examples, logs, trace attributes, and support bundles.
