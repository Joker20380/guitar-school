from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_course_is_advertised'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserequest',
            name='verification_channel',
            field=models.CharField(choices=[('email', 'Email'), ('phone', 'Phone'), ('messenger', 'Messenger')], default='email', max_length=32, verbose_name='Способ подтверждения'),
        ),
    ]
