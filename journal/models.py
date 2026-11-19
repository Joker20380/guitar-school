import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


def validate_video_url(value):
    if not value:
        return
    host = urlparse(value).netloc.lower().replace("www.", "").replace("m.", "")
    if host not in {"youtube.com", "youtu.be", "youtube-nocookie.com", "vimeo.com", "player.vimeo.com"}:
        raise ValidationError("Use a YouTube or Vimeo link.")


class Article(models.Model):
    title = models.CharField("Заголовок на английском", max_length=220)
    title_ru = models.CharField("Заголовок на русском", max_length=220, blank=True)
    slug = models.SlugField("URL-адрес", max_length=220, unique=True)
    excerpt = models.CharField("Краткое описание на английском", max_length=320, blank=True)
    excerpt_ru = models.CharField("Краткое описание на русском", max_length=320, blank=True)
    content = models.TextField("Содержание на английском")
    content_ru = models.TextField("Содержание на русском", blank=True)
    photo_url = models.URLField("Ссылка на фото", max_length=500, blank=True)
    photo_file = models.ImageField("Загрузить фото", upload_to="journal/", blank=True)
    video_url = models.URLField("Видео (необязательно)", max_length=1000, blank=True, validators=[validate_video_url])
    is_published = models.BooleanField("Показывать в блоге", default=False)
    published_at = models.DateTimeField("Дата публикации", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Статья блога"
        verbose_name_plural = "Статьи блога"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("journal:article_detail", kwargs={"slug": self.slug})

    @property
    def photo(self):
        return self.photo_file.url if self.photo_file else self.photo_url

    @property
    def video_embed_url(self):
        raw = (self.video_url or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        host = parsed.netloc.lower().replace("www.", "").replace("m.", "")
        path = parsed.path.strip("/")
        video_id = ""
        if host in {"youtube.com", "youtube-nocookie.com"}:
            if path == "watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif path.startswith(("embed/", "shorts/")):
                video_id = path.split("/", 1)[1].split("/")[0]
            if video_id and re.match(r"^[A-Za-z0-9_-]{6,64}$", video_id):
                return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"
        if host == "youtu.be":
            video_id = path.split("/")[0]
            if video_id and re.match(r"^[A-Za-z0-9_-]{6,64}$", video_id):
                return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"
        if host == "vimeo.com" and path.split("/")[0].isdigit():
            return f"https://player.vimeo.com/video/{path.split('/')[0]}"
        if host == "player.vimeo.com" and path.startswith("video/") and path.split("/")[1].isdigit():
            return f"https://player.vimeo.com/video/{path.split('/')[1]}"
        return ""
