import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Book, Author, Category


@require_http_methods(['POST'])
@login_required
def create_book(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON body.'}, status=400)

    required = ['title', 'price', 'publication_date', 'authors']
    missing = [field for field in required if field not in data]
    if missing:
        return JsonResponse({'detail': f"Missing fields: {', '.join(missing)}"}, status=400)

    try:
        pub_date = datetime.strptime(data['publication_date'], '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'detail': 'publication_date must be YYYY-MM-DD.'}, status=400)

    if data.get('isbn') and Book.objects.filter(isbn=data['isbn']).exists():
        return JsonResponse({'detail': 'ISBN already exists.'}, status=400)

    try:
        price = Decimal(str(data['price']))
        if price < 0:
            return JsonResponse({'detail': 'price must be >= 0.'}, status=400)
    except (InvalidOperation, TypeError):
        return JsonResponse({'detail': 'price must be a number.'}, status=400)

    author_ids = list(data.get('authors') or [])
    if not author_ids:
        return JsonResponse({'detail': 'At least one author is required.'}, status=400)
    authors = list(Author.objects.filter(id__in=author_ids))
    if len(authors) != len(set(author_ids)):
        return JsonResponse({'detail': 'One or more authors not found.'}, status=400)

    with transaction.atomic():
        book = Book.objects.create(
            title=data['title'],
            description=data.get('description', ''),
            price=price,
            publication_date=pub_date,
            isbn=data.get('isbn'),
            creator=request.user,
        )
        book.authors.set(authors)

    return JsonResponse(book.to_dict(), status=201)
