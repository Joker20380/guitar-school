from django.db import migrations, models
import django.db.models.deletion
import journal.models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220, verbose_name="Заголовок на английском")),
                ("title_ru", models.CharField(blank=True, max_length=220, verbose_name="Заголовок на русском")),
                ("slug", models.SlugField(max_length=220, unique=True, verbose_name="URL-адрес")),
                ("excerpt", models.CharField(blank=True, max_length=320, verbose_name="Краткое описание на английском")),
                ("excerpt_ru", models.CharField(blank=True, max_length=320, verbose_name="Краткое описание на русском")),
                ("content", models.TextField(verbose_name="Содержание на английском")),
                ("content_ru", models.TextField(blank=True, verbose_name="Содержание на русском")),
                ("photo_url", models.URLField(blank=True, max_length=500, verbose_name="Ссылка на фото")),
                ("photo_file", models.ImageField(blank=True, upload_to="journal/", verbose_name="Загрузить фото")),
                ("video_url", models.URLField(blank=True, max_length=1000, validators=[journal.models.validate_video_url], verbose_name="Видео (необязательно)")),
                ("is_published", models.BooleanField(default=False, verbose_name="Показывать в журнале")),
                ("published_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата публикации")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
            ],
            options={"ordering": ["-published_at", "-created_at"], "verbose_name": "Статья журнала", "verbose_name_plural": "Статьи журнала"},
        ),
    ]
