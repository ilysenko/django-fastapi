from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=120)


class Book(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    internal_notes = models.TextField(blank=True)
