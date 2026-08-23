from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from books.models import Book
from django_fastapi import get_current_user

router = APIRouter(tags=["books"])


class BookResponse(BaseModel):
    id: int
    title: str
    author_name: str

    @classmethod
    def from_book(cls, book: Book) -> "BookResponse":
        return cls(id=book.pk, title=book.title, author_name=book.author.name)


class SimpleBookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me")
def me(
    user: Annotated[Any, Depends(get_current_user)],
) -> dict[str, object]:
    return {
        "authenticated": bool(user.is_authenticated),
        "username": user.get_username() if user.is_authenticated else "",
    }


@router.get("/books/{book_id}/sync", response_model=BookResponse)
def get_book_sync(book_id: int) -> BookResponse:
    book = Book.objects.select_related("author").get(pk=book_id)
    return BookResponse.from_book(book)


@router.get("/books/{book_id}/async", response_model=BookResponse)
async def get_book_async(book_id: int) -> BookResponse:
    book = await Book.objects.select_related("author").aget(pk=book_id)
    return BookResponse.from_book(book)


@router.get("/books/{book_id}/simple", response_model=SimpleBookResponse)
def get_simple_book(book_id: int) -> SimpleBookResponse:
    book = Book.objects.get(pk=book_id)
    return SimpleBookResponse.model_validate(book)
