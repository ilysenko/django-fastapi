# Pydantic and Django models

Pydantic validates an API contract. It does not understand a Django model as a
database, permission, or business-rule object.

Pydantic does not automatically know:

- Django field constraints or whether `full_clean()` was called;
- which fields the current user may see;
- whether an attribute is deferred or a relation is lazy;
- whether a property will execute SQL;
- how a related manager should be serialized;
- whether a model field is safe to publish.

Keep three responsibilities separate.

## 1. Request schemas

Request schemas describe untrusted input:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    author_id: int

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title must not be blank.")
        return value
```

Use `extra="forbid"` for mutation APIs unless backward compatibility
explicitly requires unknown fields to be ignored.

## 2. Django services and models

The service layer owns authorization, transactions, Django validation, and
database constraints:

```python
def create_book(*, user, payload: BookCreatePayload) -> Book:
    if not user.has_perm("books.add_book"):
        raise PermissionDenied
    return Book.objects.create(title=payload.title, author_id=payload.author_id)
```

Pydantic success does not imply that a database operation is permitted or will
satisfy a uniqueness, foreign-key, or domain constraint.

## 3. Response schemas

Prefer an explicit mapper for application responses:

```python
from pydantic import BaseModel


class BookResponse(BaseModel):
    id: int
    title: str
    author_name: str

    @classmethod
    def from_book(cls, book: Book) -> "BookResponse":
        return cls(
            id=book.pk,
            title=book.title,
            author_name=book.author.name,
        )
```

This makes the public fields, relation access, and transformations visible in
review. It also prevents a new private model field from silently appearing in
the API.

Authorization-sensitive output should receive explicit context:

```python
class AccountResponse(BaseModel):
    username: str
    email: str | None

    @classmethod
    def from_user(cls, account, *, viewer) -> "AccountResponse":
        may_view_email = viewer.is_staff or viewer.pk == account.pk
        return cls(
            username=account.get_username(),
            email=account.email if may_view_email else None,
        )
```

## When `from_attributes` is appropriate

For a small, flat, intentionally public object, Pydantic v2 can read named
attributes:

```python
from pydantic import BaseModel, ConfigDict


class SimpleBookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


response = SimpleBookResponse.model_validate(book)
```

`from_attributes=True` is not an ORM integration. `model_validate(book)` reads
attributes. A property or relation may execute a synchronous query, including
inside an async endpoint. Load required data with `select_related()` or
`prefetch_related()` first, or use an explicit mapper.

## FastAPI response models

Always declare the response contract:

```python
@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int) -> BookResponse:
    book = Book.objects.select_related("author").get(pk=book_id)
    return BookResponse.from_book(book)
```

FastAPI validates and serializes the returned value through `response_model`.
It is useful defense in depth, but it does not replace a permission-aware
mapper.

Never return `model.__dict__`, automatically expose every model field, or use a
generic serializer for an authorization-sensitive object.
