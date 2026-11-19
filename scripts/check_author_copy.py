import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8010")
parser.add_argument("--output", default="docs/phoenix-song/full-copy-review")
args = parser.parse_args()
base = args.base_url
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
source = json.loads(Path("docs/phoenix-song/author-copy-v2.json").read_text())["blocks"]
results = []
errors = []


def text(locator):
    return re.sub(r"\s+", " ", locator.evaluate("""element => {
      const clone = element.cloneNode(true);
      clone.querySelectorAll('[aria-hidden=true]').forEach(node => node.remove());
      clone.querySelectorAll('br').forEach(node => node.replaceWith(' '));
      return clone.textContent;
    }""")).strip()


def layout(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.url
    for selector in [".body-copy", ".body-copy p", ".direction-card", ".btn:visible", ".free-note"]:
        for node in page.locator(selector).all():
            assert node.evaluate("""element => {
              const style = getComputedStyle(element);
              return element.scrollHeight <= element.clientHeight + 1
                && style.webkitLineClamp === 'none'
                && style.visibility === 'visible';
            }"""), selector
    for note in page.locator(".free-note").all():
        assert note.evaluate("element => getComputedStyle(element).color") == "rgb(229, 187, 112)"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium-browser", headless=True)
    for language in ["ru", "en"]:
        for width in [320, 390, 768, 1024, 1440]:
            context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
            context.add_cookies([{"name": "phoenix_songs_language", "value": language, "url": base}])
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            assert page.goto(base, wait_until="networkidle").status == 200
            page.evaluate("document.fonts.ready")
            checked = 0
            for block in list(source.values())[:7]:
                container = page.locator(block["selector"])
                for selector, expected in block["fields"].items():
                    node = container.locator(selector)
                    expect(node).to_have_count(1)
                    if isinstance(expected, list):
                        paragraphs = node.locator(":scope > p")
                        expect(paragraphs).to_have_count(len(expected))
                        if language == "ru":
                            assert [text(paragraph) for paragraph in paragraphs.all()] == expected
                    elif language == "ru":
                        assert text(node) == expected, (width, selector, text(node), expected)
                    checked += 1
            for stack in page.locator(".cta-stack").all():
                first, second = [node.bounding_box() for node in stack.locator(".btn").all()]
                assert first["y"] + first["height"] <= second["y"]
            layout(page)
            phone = page.locator(".footer-contact .phone")
            assert phone.evaluate("element => getComputedStyle(element).whiteSpace") == "nowrap"
            assert page.goto(base + "/contacts/trial/", wait_until="networkidle").status == 200
            expect(page.locator("#id_preferred_contact")).to_have_value("whatsapp")
            expect(page.locator("input[name=email]")).to_have_count(0)
            for channel in ["telegram", "other", "whatsapp", "other"]:
                page.locator("#id_preferred_contact").select_option(channel)
                for field, value in [("telegram", "telegram"), ("other_contact", "other")]:
                    assert page.locator("#id_" + field).is_visible() == (channel == value)
                    assert page.locator("#id_" + field).is_enabled() == (channel == value)
            for selector, expected in source["A8"]["fields"].items():
                if selector.startswith(".success-card"):
                    continue
                if language == "ru":
                    assert text(page.locator(selector)) == expected, (selector, text(page.locator(selector)))
                checked += 1
            page.locator("[data-submit]").click()
            expect(page.locator("[data-dynamic-errors]")).to_be_visible()
            layout(page)
            page.locator("#id_name").fill("Élodie Müller")
            page.locator("#id_direction").select_option("undecided")
            page.locator("#id_phone").fill("+33142345678")
            page.locator("#id_other_contact").fill("synthetic-long-contact-for-layout@example.com")
            if width in [390, 1440]:
                page.screenshot(path=str(output / f"conditional-form-{language}-{width}.png"), full_page=True)
            page.locator("[data-submit]").click()
            page.wait_for_url("**/contacts/trial/success/")
            if language == "ru":
                assert text(page.locator(".success-card h1")) == source["A8"]["fields"][".success-card h1"]
            checked += 1
            layout(page)
            if width == 390:
                page.screenshot(path=str(output / f"success-{language}-{width}.png"), full_page=True)
            context.add_cookies([{"name": "phoenix_songs_language", "value": "en", "url": base}])
            assert page.goto(base + "/journal/", wait_until="networkidle").status == 200
            for selector, expected in source["A9"]["fields"].items():
                assert text(page.locator(selector)) == expected
                checked += 1
            assert checked == 31
            results.append({"locale": language, "width": width, "fields": checked, "russian_exact_comparison": language == "ru", "paragraph_counts": [3, 1, 3, 5, 5, 2, 2], "layout_and_form": "PASS"})
            print("PASS", language, width, "31 fields / paragraph structure / form / gold notes", flush=True)
            context.close()
    browser.close()
assert not errors, errors
(output / "author-copy-checks.json").write_text(json.dumps({"base": base, "results": results, "javascript_errors": errors}, ensure_ascii=False, indent=2) + "\n")
