from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactmessage',
            name='direction',
            field=models.CharField(blank=True, choices=[('russian', 'Russian through music'), ('guitar', 'Guitar and musical creativity'), ('undecided', "I haven't decided yet")], max_length=20, verbose_name='Направление'),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='email_notification_status',
            field=models.CharField(choices=[('disabled', 'Отключено'), ('accepted', 'Принято сервисом, доставка не подтверждена'), ('failed', 'Ошибка')], default='disabled', max_length=12, verbose_name='Email уведомление'),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='other_contact',
            field=models.CharField(blank=True, max_length=200, verbose_name='Другой контакт'),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='submission_key',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True, verbose_name='Ключ отправки'),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='telegram_notification_status',
            field=models.CharField(choices=[('disabled', 'Отключено'), ('accepted', 'Принято сервисом, доставка не подтверждена'), ('failed', 'Ошибка')], default='disabled', max_length=12, verbose_name='Telegram уведомление'),
        ),
        migrations.AlterField(
            model_name='contactmessage',
            name='preferred_contact',
            field=models.CharField(choices=[('email', 'Email'), ('phone', 'Phone'), ('telegram', 'Telegram'), ('whatsapp', 'WhatsApp'), ('other', 'Another way')], default='email', max_length=32, verbose_name='Удобный способ связи'),
        ),
        migrations.AlterField(
            model_name='contactmessage',
            name='status',
            field=models.CharField(choices=[('new', 'New'), ('replied', 'Replied'), ('archived', 'Archived')], default='new', max_length=32, verbose_name='Статус'),
        ),
    ]
