"""Upload validation and storage for public images and private course materials."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator, URLValidator
from django.urls import reverse
from django.utils.deconstruct import deconstructible


validate_resource_url = URLValidator(schemes=["http", "https"])
validate_image_extension = FileExtensionValidator(["jpg", "jpeg", "png", "webp"])
validate_video_extension = FileExtensionValidator(["mp4", "webm"])
validate_material_extension = FileExtensionValidator([
    "pdf", "txt", "doc", "docx", "odt", "ppt", "pptx", "xls", "xlsx",
    "jpg", "jpeg", "png", "webp", "mp3", "wav", "ogg", "m4a", "flac",
    "mp4", "webm", "zip", "gp", "gp3", "gp4", "gp5", "gpx", "gp7",
    "musicxml", "mxl", "mscz", "mscx", "mid", "midi",
])


def validate_image_size(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Изображение должно быть не больше 5 МБ.")


def validate_material_size(value):
    if value.size > 15 * 1024 * 1024:
        raise ValidationError("Файл должен быть не больше 15 МБ. Для больших файлов используйте ссылку.")


def public_image_path(instance, filename):
    return f"images/{uuid4().hex}{Path(filename).suffix.lower()}"


def private_material_path(instance, filename):
    return f"materials/{uuid4().hex}/{Path(filename).name}"


@deconstructible
class PrivateMaterialStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    def url(self, name):
        return reverse("courses:private_file", kwargs={"name": name})


private_storage = PrivateMaterialStorage()
