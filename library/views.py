import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Book, Author


@require_http_methods(['GET', 'POST'])
def books(request):
    if request.method == 'GET':
        title = request.GET.get('title')
        author = request.GET.get('author')
        category_slug = request.GET.get('category')
        price_min = request.GET.get('price_min')
        price_max = request.GET.get('price_max')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        qs = Book.objects.all()

        if title:
            qs = qs.filter(title__icontains=title)

        if author:
            qs = qs.filter(authors__name__icontains=author)

        if category_slug:
            if not request.user.is_authenticated:
                return JsonResponse({'detail': 'Authentication required for category-based listing.'}, status=401)
            qs = qs.filter(categories__slug=category_slug, categories__owner=request.user)

        qs = qs.distinct()

        if price_min not in (None, ''):
            try:
                qs = qs.filter(price__gte=Decimal(str(price_min)))
            except (InvalidOperation, TypeError):
                return JsonResponse({'detail': 'price_min must be a number.'}, status=400)

        if price_max not in (None, ''):
            try:
                qs = qs.filter(price__lte=Decimal(str(price_max)))
            except (InvalidOperation, TypeError):
                return JsonResponse({'detail': 'price_max must be a number.'}, status=400)

        if date_from:
            try:
                dfrom = datetime.strptime(date_from, '%Y-%m-%d').date()
                qs = qs.filter(publication_date__gte=dfrom)
            except ValueError:
                return JsonResponse({'detail': 'date_from must be YYYY-MM-DD.'}, status=400)

        if date_to:
            try:
                dto = datetime.strptime(date_to, '%Y-%m-%d').date()
                qs = qs.filter(publication_date__lte=dto)
            except ValueError:
                return JsonResponse({'detail': 'date_to must be YYYY-MM-DD.'}, status=400)

        try:
            page = int(request.GET.get('page', '1'))
            page_size = int(request.GET.get('page_size', '20'))
        except ValueError:
            return JsonResponse({'detail': 'page and page_size must be integers.'}, status=400)

        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size

        qs = qs.select_related('creator').prefetch_related('authors', 'categories', 'favorited_by')[start:end]
        items = [book.to_dict() for book in qs]

        return JsonResponse({'count': total, 'page': page, 'page_size': page_size, 'results': items}, status=200)

    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

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

@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def book_detail(request, book_id):
    try:
        book = Book.objects.select_related('creator').prefetch_related('authors', 'categories', 'favorited_by').get(pk=book_id)
    except ObjectDoesNotExist:
        return JsonResponse({'detail': 'Book not found.'}, status=404)

    if request.method == 'GET':
        return JsonResponse(book.to_dict(), status=200)

    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    if not (request.user.is_staff or book.creator_id == request.user.id):
        return JsonResponse({'detail': 'You do not have permission to modify this book.'}, status=403)

    if request.method == 'DELETE':
        book.delete()
        return JsonResponse({'detail': 'Book deleted successfully.'}, status=204)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON body.'}, status=400)

    if 'title' in data:
        book.title = data['title']

    if 'description' in data:
        book.description = data['description'] or ''

    if 'price' in data:
        try:
            price = Decimal(str(data['price']))
            if price < 0:
                return JsonResponse({'detail': 'price must be >= 0.'}, status=400)
            book.price = price
        except (InvalidOperation, TypeError):
            return JsonResponse({'detail': 'price must be a number.'}, status=400)

    if 'publication_date' in data:
        try:
            book.publication_date = datetime.strptime(data['publication_date'], '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'detail': 'publication_date must be YYYY-MM-DD.'}, status=400)

    if 'isbn' in data:
        new_isbn = data['isbn']
        if new_isbn:
            if Book.objects.filter(isbn=new_isbn).exclude(pk=book.id).exists():
                return JsonResponse({'detail': 'ISBN already exists.'}, status=400)
            book.isbn = new_isbn
        else:
            book.isbn = None

    if 'authors' in data:
        ids = list(data.get('authors') or [])
        if not ids:
            return JsonResponse({'detail': 'At least one author is required.'}, status=400)
        authors = list(Author.objects.filter(id__in=ids))
        if len(authors) != len(set(ids)):
            return JsonResponse({'detail': 'One or more authors not found.'}, status=400)
        set_authors_after_save = authors
    else:
        set_authors_after_save = None


    book.save()

    if set_authors_after_save is not None:
        book.authors.set(set_authors_after_save)

    book = Book.objects.select_related('creator').prefetch_related('authors', 'categories', 'favorited_by').get(pk=book_id)
    return JsonResponse(book.to_dict(), status=200)
