from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.utils import translation


class LocaleFilesystemLoader(FilesystemLoader):
    """Load a locale-specific template first, then the English source template."""

    def get_dirs(self):
        dirs = list(super().get_dirs())
        language = (translation.get_language() or settings.LANGUAGE_CODE).split("-")[0]
        if language == "ru":
            return [settings.BASE_DIR / "templates" / "ru", *dirs]
        return dirs
