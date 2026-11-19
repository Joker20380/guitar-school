from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0007_course_cover_file_lesson_video_file_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='is_advertised',
            field=models.BooleanField(default=False, help_text='Не влияет на доступ уже зачисленных учеников.', verbose_name='Рекламировать публично'),
        ),
    ]
