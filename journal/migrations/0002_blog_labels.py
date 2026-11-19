from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("journal", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(
            name="article",
            options={
                "ordering": ["-published_at", "-created_at"],
                "verbose_name": "Статья блога",
                "verbose_name_plural": "Статьи блога",
            },
        ),
        migrations.AlterField(
            model_name="article",
            name="is_published",
            field=models.BooleanField("Показывать в блоге", default=False),
        ),
    ]
