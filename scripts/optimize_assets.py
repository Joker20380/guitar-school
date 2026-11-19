from pathlib import Path
from PIL import Image

source = Path("static/images/phoenix-song-logo.png")
destination = Path("static/images/branding/phoenix-footer-640.webp")
with Image.open(source) as image:
    image.thumbnail((640, 320), Image.Resampling.LANCZOS)
    image.save(destination, format="WEBP", quality=90, method=6)
print(f"Original preserved; footer copy: {destination.stat().st_size} bytes")
