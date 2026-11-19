import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--stage", default="intermediate")
parser.add_argument("--base-url", default="http://127.0.0.1:8007")
args = parser.parse_args()
destination = Path("docs/phoenix-song/screenshots")
destination.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium-browser", headless=True)
    for language in ["en", "ru"]:
        for width in [390, 1440]:
            context = browser.new_context(viewport={"width": width, "height": 1000}, device_scale_factor=1)
            context.add_cookies([{"name": "phoenix_songs_language", "value": language, "url": args.base_url}])
            page = context.new_page()
            response = page.goto(args.base_url, wait_until="networkidle")
            assert response.status == 200, response.status
            page.evaluate("document.fonts.ready")
            for position in range(0, page.evaluate("document.body.scrollHeight"), 700):
                page.evaluate("position => window.scrollTo({top:position,behavior:'instant'})", position)
                page.wait_for_timeout(80)
            page.wait_for_timeout(500)
            page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
            page.wait_for_timeout(500)
            page.screenshot(path=str(destination / f"{args.stage}-home-{language}-{width}.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (language, width, "horizontal overflow")
            context.close()
    browser.close()
print("Captured running Django homepage in both locales at 390/1440px")
