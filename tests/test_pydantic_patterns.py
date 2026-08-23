from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync
from django_fastapi_testproject.books.models import Author, Book
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.testclient import TestClient


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


class BookResponse(BaseModel):
    id: int
    title: str
    author_name: str

    @classmethod
    def from_book(cls, book: Book) -> BookResponse:
        return cls(id=book.pk, title=book.title, author_name=book.author.name)


class SimpleBookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class AccountResponse(BaseModel):
    username: str
    email: str | None

    @classmethod
    def from_account(
        cls,
        *,
        username: str,
        email: str,
        viewer_may_read_email: bool,
    ) -> AccountResponse:
        return cls(
            username=username,
            email=email if viewer_may_read_email else None,
        )


def test_request_schema_cleans_input_and_forbids_unknown_fields() -> None:
    payload = BookCreatePayload.model_validate({"title": "  A book  ", "author_id": 4})

    assert payload.title == "A book"
    with pytest.raises(ValidationError):
        BookCreatePayload.model_validate(
            {"title": "A book", "author_id": 4, "internal_notes": "private"}
        )


@pytest.mark.django_db
def test_explicit_mapper_does_not_expose_private_model_state() -> None:
    author = Author.objects.create(name="Ada Example")
    book = Book.objects.create(
        title="A book",
        author=author,
        internal_notes="never publish this",
    )
    record = Book.objects.select_related("author").get(pk=book.pk)

    response = BookResponse.from_book(record)

    assert response.model_dump() == {
        "id": 1,
        "title": "A book",
        "author_name": "Ada Example",
    }
    assert "internal_notes" not in response.model_dump()


@pytest.mark.django_db
def test_from_attributes_is_limited_to_declared_flat_fields() -> None:
    author = Author.objects.create(name="Grace Example")
    record = Book.objects.create(
        title="Another book",
        author=author,
        internal_notes="private",
    )

    response = SimpleBookResponse.model_validate(record)

    assert response.model_dump() == {"id": record.pk, "title": "Another book"}


@pytest.mark.django_db(transaction=True)
def test_async_orm_mapper_uses_aquery_and_preloaded_relation() -> None:
    async def fetch_response() -> tuple[BookResponse, int]:
        author = await Author.objects.acreate(name="Async Author")
        created = await Book.objects.acreate(
            title="Async ORM",
            author=author,
            internal_notes="private",
        )

        record = await Book.objects.select_related("author").aget(pk=created.pk)
        return BookResponse.from_book(record), created.pk

    response, book_id = async_to_sync(fetch_response)()

    assert response.model_dump() == {
        "id": book_id,
        "title": "Async ORM",
        "author_name": "Async Author",
    }


def test_permission_aware_mapper_hides_email() -> None:
    response = AccountResponse.from_account(
        username="reader",
        email="reader@example.test",
        viewer_may_read_email=False,
    )

    assert response.model_dump() == {"username": "reader", "email": None}


def test_fastapi_response_model_filters_undeclared_fields() -> None:
    app = FastAPI()

    @app.get("/book", response_model=SimpleBookResponse)
    def book() -> dict[str, object]:
        return {"id": 3, "title": "Filtered", "internal_notes": "private"}

    response = TestClient(app).get("/book")

    assert response.status_code == 200
    assert response.json() == {"id": 3, "title": "Filtered"}
