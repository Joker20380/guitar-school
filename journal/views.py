from django.shortcuts import get_object_or_404, render

from .models import Article


def article_list(request):
    return render(request, "journal/article_list.html", {
        "articles": Article.objects.filter(is_published=True),
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    return render(request, "journal/article_detail.html", {"article": article})
