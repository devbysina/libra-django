from django.urls import path
from .views import books, book_detail

urlpatterns = [
    path('api/books/', books, name='books'),
    path('api/books/<int:book_id>/', book_detail, name='book-detail')
]