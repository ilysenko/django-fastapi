from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from books.models import Author, Book


class Command(BaseCommand):
    help = "Create one example author and book."

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(username="reader")
        user.set_password("local-example-password")
        user.save(update_fields=["password"])
        author, _ = Author.objects.get_or_create(name="Ada Example")
        book, _ = Book.objects.get_or_create(
            author=author,
            title="ASGI for Django Developers",
            defaults={"internal_notes": "This value is never exposed by the API."},
        )
        self.stdout.write(self.style.SUCCESS(f"Book id: {book.pk}"))
