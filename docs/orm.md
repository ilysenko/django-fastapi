# Django ORM: sync and async

The ASGI server and the endpoint function are separate choices. Pick the
endpoint style based on the code it calls.

## Synchronous endpoint

FastAPI runs `def` operations in a worker thread. Use the normal Django ORM:

```python
@router.get("/books/{book_id}", response_model=BookResponse)
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
from asgiref.sync import sync_to_async
from django.db import transaction


@transaction.atomic
def checkout_sync(user, payload):
    ...


@router.post("/checkout")
async def checkout(user: AuthenticatedUser, payload: CheckoutPayload):
    return await sync_to_async(checkout_sync, thread_sensitive=True)(user, payload)
```

Do not set `DJANGO_ALLOW_ASYNC_UNSAFE` in production. It disables Django's
safety check rather than making blocking code asynchronous.

This boundary follows Django's own
[asynchronous support guidance](https://docs.djangoproject.com/en/6.1/topics/async/):
keep a transaction or other synchronous workflow inside one synchronous
function, then call that function with
`sync_to_async(..., thread_sensitive=True)`.

## Query planning before serialization

Pydantic may read attributes and properties while creating the response.
Load every relation the response mapper needs before entering it:

```python
book = await Book.objects.select_related("author").aget(pk=book_id)
return BookResponse.from_book(book)
```

For collections, use `prefetch_related()` before async iteration. Measure query
counts in tests so a schema change does not accidentally create an N+1 query.
