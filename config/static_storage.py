from urllib.parse import urljoin
from whitenoise.storage import CompressedManifestStaticFilesStorage


class AdminStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Jazzmin builds theme URLs from a directory; real files still use strict hashes."""

    def url(self, name, force=False):
        if name == "vendor/bootswatch":
            return urljoin(self.base_url, "vendor/bootswatch")
        return super().url(name, force=force)
