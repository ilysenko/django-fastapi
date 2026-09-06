# Django ORM: sync and async

The ASGI server and the endpoint function are separate choices. Pick the
endpoint style based on the code it calls.

## Synchronous endpoint

FastAPI runs `def` operations in a worker thread. Use the normal Django ORM:

```python
from django_fastapi import django_db


@router.get("/books/{book_id}", response_model=BookResponse)
@django_db
def get_book(book_id: int) -> BookResponse:
    book = Book.objects.select_related("author").get(pk=book_id)
    return BookResponse.from_book(book)
```

This is often the safest option for established service code, transactions,
and third-party Django libraries that are synchronous.

## Asynchronous endpoint

Use async ORM methods for every operation that executes SQL:

```python
@router.get("/books/{book_id}", response_model=BookResponse)
async def get_book(book_id: int) -> BookResponse:
    book = await Book.objects.select_related("author").aget(pk=book_id)
    return BookResponse.from_book(book)
```

Other examples include `aexists()`, `afirst()`, `acreate()`, `asave()`, and
`async for item in queryset`.

Do not call `Book.objects.get()` from `async def`. Django will normally raise
`SynchronousOnlyOperation` to protect the event loop.

## Synchronous services from async endpoints

Keep a transactional workflow in one synchronous function and cross the
boundary once:

```python
from django_fastapi import database_sync_to_async
from django.db import transaction


@transaction.atomic
def checkout_sync(user, payload):
    ...


@router.post("/checkout")
async def checkout(user: AuthenticatedUser, payload: CheckoutPayload):
    return await database_sync_to_async(checkout_sync)(user, payload)
```

Do not set `DJANGO_ALLOW_ASYNC_UNSAFE` in production. It disables Django's
safety check rather than making blocking code asynchronous.

This boundary follows Django's own
[asynchronous support guidance](https://docs.djangoproject.com/en/6.1/topics/async/):
keep a transaction or other synchronous workflow inside one synchronous
function, then call that function with
`database_sync_to_async(...)`, which preserves `thread_sensitive=True` and
returns the thread's database leases in `finally`.

## Connection ownership

Created HTTP apps install a pure ASGI middleware with a separate
`ThreadSensitiveContext` per request. Cleanup runs on that executor before
streaming response headers and at completion, including errors and cancellation.
Session changes are persisted before headers. This does not automatically clean
FastAPI's unrelated AnyIO sync worker threads: decorate ORM-using synchronous
handlers **and dependencies** with `@django_db` (inside the route decorator).
Signatures are preserved, and all initialized Django aliases are covered.
`django_db` accepts ordinary synchronous functions only. It rejects generator
(`yield`) dependencies and async functions at decoration time: their work would
otherwise execute after the cleanup boundary had already exited. For a `yield`
dependency, put each short ORM operation in a separate decorated sync helper;
do not keep a transaction or lease across the yield.

Use `await aclose_db_connections()` before a long external await after async
ORM work, and in an async stream's `finally` block. For WebSockets, use
`database_sync_to_async` around each short DB operation; never reserve a
connection for the socket's lifetime. None of these helpers closes a connection
inside an active atomic block: finish transactions before external waits.

Set `CONN_MAX_AGE=0` under ASGI. On supported PostgreSQL/psycopg installations,
Django's `DATABASES["default"]["OPTIONS"]["pool"]` configures a bounded native
pool; close then returns a lease rather than necessarily disconnecting TCP.
Shared helpers preserve healthy persistent connections when `CONN_MAX_AGE` is
nonzero (for example in WSGI/Celery); only obsolete or unusable ones are closed.
The host application owns pool sizing, overload responses, monitoring, and
shutdown. The bridge does not create or globally monkeypatch a pool/executor.

## Query planning before serialization

Pydantic may read attributes and properties while creating the response.
Load every relation the response mapper needs before entering it:

```python
book = await Book.objects.select_related("author").aget(pk=book_id)
return BookResponse.from_book(book)
```

For collections, use `prefetch_related()` before async iteration. Measure query
counts in tests so a schema change does not accidentally create an N+1 query.
