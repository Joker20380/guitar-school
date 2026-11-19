from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("contacts", "0002_contactmessage_direction_and_more")]

    operations = [
        migrations.AlterField(
            model_name="contactmessage",
            name="message",
            field=models.TextField("Сообщение", blank=True),
        ),
    ]
