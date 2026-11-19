import courses.media
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Имя')),
                ('text', models.TextField(max_length=3000, verbose_name='Отзыв')),
                ('photo', models.ImageField(blank=True, upload_to='reviews/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), courses.media.validate_image_size], verbose_name='Фото (необязательно)')),
                ('is_published', models.BooleanField(default=False, verbose_name='Опубликован')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Отзыв',
                'verbose_name_plural': 'Отзывы',
                'ordering': ['-created_at'],
            },
        ),
    ]
