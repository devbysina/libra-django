from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    birth_date = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True, validators=[MinValueValidator(0)],
                                default=0)
    publication_date = models.DateField(db_index=True)

    isbn = models.CharField(max_length=20, null=True, blank=True, unique=True)

    authors = models.ManyToManyField(Author, related_name="books")
    categories = models.ManyToManyField(Category, related_name="books", blank=True)

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_books"
    )

    favorited_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="favorite_books",
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
