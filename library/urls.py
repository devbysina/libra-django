from django.urls import path
from .views import create_book

urlpatterns = [
    path('api/books/', create_book, name='book-create'),
]