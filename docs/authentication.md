# Authentication, sessions, and CSRF

## Django request

Inject a Django-compatible request when existing services expect
`django.http.HttpRequest`:

```python
from typing import Annotated

from django.http import HttpRequest
from fastapi import Depends
from django_fastapi import get_django_request

DjangoRequest = Annotated[HttpRequest, Depends(get_django_request)]
```

The adapter constructs one request per FastAPI request and caches it. It sets
up Django's configured session backend and resolves `request.user`.

## Built-in user dependencies

- `get_current_user`: authenticated user or `AnonymousUser`.
- `get_authenticated_user`: authenticated user or HTTP 401.
- `get_current_staff_user`: staff user or HTTP 401/403.

The package cannot know a project's concrete custom user class. Projects may
wrap these dependencies and perform an `isinstance` check or cast locally.

## Session authentication

The default resolver runs Django's normal session authentication. The FastAPI
and Django paths must receive the same session cookie. Separate services must
share the session backend, `SECRET_KEY`, cookie name, domain, path, security,
and SameSite settings.

Session changes made through the adapted request are saved back onto the
FastAPI response:

```python
@router.post("/preferences")
def update_preferences(request: DjangoRequest) -> dict[str, bool]:
    request.session["compact_mode"] = True
    return {"saved": True}
```

## Custom authentication resolver

A resolver receives `(fastapi_request, django_request)`, may be sync or async,
and returns a Django user, `AnonymousUser`, or `None`. The first authenticated
user wins. `None` and anonymous users allow the next resolver to run.

```python
from django.contrib.auth import get_user_model
from fastapi import Request


async def bearer_resolver(request: Request, _django_request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not token:
        return None

    subject = await verify_token_and_get_subject(token)
    return await get_user_model().objects.aget(external_id=subject)
```

```python
"AUTH_RESOLVERS": [
    "project.auth.bearer_resolver",
    "django_fastapi.auth.session_auth_resolver",
]
```

The resolver owns signature, issuer, audience, expiry, revocation, and scope
validation. The bridge deliberately does not implement token policy.

## CSRF

CSRF is enabled by default for `POST`, `PUT`, `PATCH`, and `DELETE`. Django's
normal `csrftoken` cookie and `X-CSRFToken` header work.

Keep CSRF enabled whenever a browser can authenticate with a cookie. Disabling
CSRF is appropriate only when an endpoint cannot use cookie authentication and
has another complete request-authentication mechanism.

Exempt one operation:

```python
from django_fastapi import csrf_exempt


@router.post("/provider-webhook")
@csrf_exempt
def webhook():
    ...
```

The endpoint must then validate the provider signature itself.
