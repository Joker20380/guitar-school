import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8009")
parser.add_argument("--output", type=Path, default=Path(".preview/followup"))
options = parser.parse_args()
options.output.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium-browser", headless=True)
    for width in [320, 390, 768, 1024, 1440]:
        context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
        page = context.new_page()
        page.goto(options.base_url + "/tuner/", wait_until="networkidle")
        for language in ["en", "ru", "en"]:
            page.locator(f'.language-switch [value="{language}"]').click()
            page.wait_for_load_state("networkidle")
            assert page.locator("html").get_attribute("lang") == language
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (width, language, "page overflow")
            failures = page.evaluate("""() => {
                const selectors = ['.tuner-card', '.instrument-panel', '.side-instruments', '.string-display', '.vu-meter', '.vu-labels', '.reference-pitch', '.microphone-control', '.microphone-slider', '.microphone-level', '.metronome-panel', '.metronome-heading', '.metronome-display', '.metronome-tempo'];
                return selectors.flatMap(selector => [...document.querySelectorAll(selector)].flatMap(parent => {
                    const bounds = parent.getBoundingClientRect();
                    return [...parent.children].filter(child => {
                        const rect = child.getBoundingClientRect();
                        return rect.width && (rect.left < bounds.left - 1 || rect.right > bounds.right + 1);
                    }).map(child => selector + ' > ' + child.tagName + '.' + child.className);
                }));
            }""")
            assert not failures, (width, language, failures)
            for frequency in ["440", "432"]:
                page.locator(f'[data-reference-pitch="{frequency}"]').click()
                assert frequency in page.locator("#referencePitchValue").inner_text()
                assert page.locator('.reference-pitch-button[aria-pressed="true"]').count() == 1
            page.locator("#tempoInput").fill("120")
            page.locator("#tempoInput").press("Tab")
            page.locator("#tempoUp").click()
            assert page.locator("#tempoInput").input_value() == "121"
            page.locator("#tempoDown").click()
            assert page.locator("#tempoInput").input_value() == "120"
            icon = page.locator('link[rel="icon"]').get_attribute("href")
            response = context.request.get(options.base_url + icon)
            assert response.status == 200 and response.headers["content-type"].startswith("image/")
            fallback = context.request.get(options.base_url + "/favicon.ico")
            assert fallback.status == 200 and fallback.headers["content-type"].startswith("image/")
            results.append({"width": width, "language": language, "nested_grid_containment": "PASS", "reference_switch": "PASS", "tempo_controls": "PASS", "favicon": "PASS"})
            if width in [390, 1440]:
                page.screenshot(path=str(options.output / f"tuner-{language}-{width}.png"), full_page=True)
        context.close()
    browser.close()
(options.output / "tuner-layout.json").write_text(json.dumps(results, indent=2) + "\n")
print(f"PASS: {len(results)} EN/RU language-switch/layout/favicon checks; microphone not used")
