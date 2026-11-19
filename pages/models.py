from django.db import models
from django.conf import settings
from courses.media import validate_image_extension, validate_image_size

class Review(models.Model):
    name = models.CharField("Имя", max_length=120)
    text = models.TextField("Отзыв", max_length=3000)
    photo = models.ImageField("Фото (необязательно)", upload_to="reviews/", blank=True, validators=[validate_image_extension, validate_image_size])
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ученик")
    is_published = models.BooleanField("Опубликован", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return self.name
