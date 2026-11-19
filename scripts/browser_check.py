import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.preview_settings"
import django
django.setup()

from django.core import signing
from django.db import close_old_connections
from playwright.sync_api import expect, sync_playwright
from contacts.models import ContactMessage
from contacts.trial import TOKEN_SALT

BASE = "http://127.0.0.1:8008"
OUTPUT = Path("docs/phoenix-song/screenshots")
OUTPUT.mkdir(parents=True, exist_ok=True)
CREDENTIALS = json.loads(Path(".preview/access.json").read_text())
results = []
errors = []


def record(label):
    results.append(label)
    print("PASS", label, flush=True)


def saved_rows(key):
    def read():
        close_old_connections()
        try:
            return list(ContactMessage.objects.filter(submission_key=key).values("pk"))
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(read).result()


def navigate(page, path):
    response = page.goto(BASE + path, wait_until="networkidle")
    assert response.status == 200, (path, response.status)
    page.evaluate("document.fonts.ready")


def layout(page, label):
    overflow = page.evaluate("""() => {
      if (document.documentElement.scrollWidth <= innerWidth + 1) return [];
      return [...document.querySelectorAll('body *')].filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.width && (rect.right > innerWidth + 1 || rect.left < -1);
      }).slice(0, 8).map(element => element.tagName + '.' + element.className);
    }""")
    assert not overflow, (label, overflow)
    for button in page.locator(".btn:visible").all():
        box = button.bounding_box()
        assert box["width"] > 0 and box["x"] >= -1 and box["x"] + box["width"] <= page.viewport_size["width"] + 1, label


def screenshot(page, filename):
    for position in range(0, page.evaluate("document.body.scrollHeight"), 700):
        page.evaluate("position => scrollTo({top:position,behavior:'instant'})", position)
        page.wait_for_timeout(60)
    page.wait_for_timeout(300)
    page.evaluate("scrollTo({top:0,behavior:'instant'})")
    page.screenshot(path=str(OUTPUT / filename), full_page=True)


def fill_trial(page, name="Élodie Test"):
    page.locator("#id_name").fill(name)
    page.locator("#id_direction").select_option("undecided")
    page.locator("#id_phone").fill("+442079460958")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium-browser", headless=True)
    fresh = browser.new_context(locale="ru-RU", viewport={"width": 390, "height": 900})
    page = fresh.new_page()
    navigate(page, "/")
    assert page.locator("html").get_attribute("lang") == "en"
    page.locator(".language-switch [value=ru]").click()
    page.wait_for_load_state("networkidle")
    assert page.locator("html").get_attribute("lang") == "ru"
    navigate(page, "/contacts/")
    assert page.locator("html").get_attribute("lang") == "ru"
    page.locator(".language-switch [value=en]").click()
    page.wait_for_load_state("networkidle")
    assert page.locator("html").get_attribute("lang") == "en"
    record("Fresh RU browser starts EN; explicit RU/EN choice persists")
    fresh.close()

    routes = ["/", "/journal/", "/journal/preview-first-chord/", "/contacts/", "/contacts/trial/", "/reviews/", "/accounts/login/", "/accounts/password_reset/", "/tuner/"]
    for language in ["en", "ru"]:
        for width in [390, 1440]:
            context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
            context.add_cookies([{"name": "phoenix_songs_language", "value": language, "url": BASE}])
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for route in routes:
                navigate(page, route)
                layout(page, (language, width, route))
                assert page.locator("html").get_attribute("lang") == language
                if route == "/":
                    assert page.locator(".direction-card").count() == 2
                    sections = page.locator("main>section").evaluate_all("items => items.map(item => item.id)")
                    assert sections == ["welcome", "directions", "story", "community", "start"], sections
                    for group in page.locator(".cta-stack").all():
                        buttons = group.locator(".btn").all()
                        first, second = [button.bounding_box() for button in buttons]
                        assert first["y"] + first["height"] <= second["y"]
                    screenshot(page, f"final-home-{language}-{width}.png")
                if route == "/contacts/trial/":
                    screenshot(page, f"final-form-{language}-{width}.png")
                if language == "en" and width == 1440 and route == "/journal/preview-first-chord/":
                    screenshot(page, "final-article-en-1440.png")
            navigate(page, "/")
            targets = page.locator('a[href^="/contacts/trial/"]:visible').evaluate_all("links => links.map(link => link.getAttribute('href'))")
            assert len(targets) == 6, targets
            for index, target in enumerate(targets):
                page.locator('a[href^="/contacts/trial/"]:visible').nth(index).click()
                page.wait_for_url("**/contacts/trial/**")
                expected_direction = target.split("direction=")[1] if "direction=" in target else ""
                expect(page.locator("#id_direction")).to_have_value(expected_direction)
                navigate(page, "/")
            navigate(page, "/accounts/login/")
            page.locator("#id_username").fill(CREDENTIALS["student"])
            page.locator("#id_password").fill(CREDENTIALS["password"])
            page.locator(".course-submit").click()
            page.wait_for_url("**/courses/my/")
            layout(page, (language, width, "student area"))
            if language == "en" and width == 1440:
                screenshot(page, "final-student-en-1440.png")
            navigate(page, "/courses/my/preview-guitar/")
            layout(page, (language, width, "student lesson"))
            assert "Hidden draft" not in page.locator("main").inner_text()
            navigate(page, "/reviews/new/")
            layout(page, (language, width, "review form"))
            record(f"{language} {width}px: nine public pages, login, dashboard, protected lesson, review form")
            context.close()

    for language in ["en", "ru"]:
        for width in [320, 768, 1024]:
            context = browser.new_context(viewport={"width": width, "height": 950}, reduced_motion="reduce")
            context.add_cookies([{"name": "phoenix_songs_language", "value": language, "url": BASE}])
            page = context.new_page()
            navigate(page, "/")
            layout(page, (language, width, "home"))
            assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"
            page.keyboard.press("Tab")
            assert page.locator(".skip-link").evaluate("element => element === document.activeElement")
            assert page.locator(".skip-link").evaluate("element => getComputedStyle(element).outlineStyle") != "none"
            toggle = page.locator("[data-mobile-toggle]")
            toggle.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#mobile-menu")).to_be_visible()
            layout(page, (language, width, "open menu"))
            if language == "ru" and width == 320:
                screenshot(page, "final-menu-ru-320.png")
            page.keyboard.press("Escape")
            expect(page.locator("#mobile-menu")).to_be_hidden()
            assert toggle.evaluate("element => element === document.activeElement")
            for direction in ["russian", "guitar"]:
                page.locator(f'a[href="/contacts/trial/?direction={direction}"]').click()
                expect(page.locator("#id_direction")).to_have_value(direction)
                layout(page, (language, width, direction))
                navigate(page, "/")
            page.locator(".header-cta").click()
            expect(page.locator("#id_direction")).to_have_value("")
            assert page.locator('input[name="email"]').count() == 0
            page.locator("#id_preferred_contact").select_option("telegram")
            expect(page.locator("#id_telegram")).to_be_visible()
            expect(page.locator("#id_telegram")).to_be_enabled()
            page.locator("#id_preferred_contact").select_option("other")
            expect(page.locator("#id_telegram")).to_be_hidden()
            expect(page.locator("#id_other_contact")).to_be_visible()
            page.locator("#id_preferred_contact").select_option("whatsapp")
            page.locator("[data-submit]").click()
            expect(page.locator("[data-dynamic-errors]")).to_be_visible()
            layout(page, (language, width, "errors"))
            if width == 320 and language == "ru":
                screenshot(page, "final-form-errors-ru-320.png")
            record(f"{language} {width}px: keyboard, menu, reduced motion, both cards, reset, conditional fields, errors")
            context.close()

    context = browser.new_context(viewport={"width": 390, "height": 950})
    page = context.new_page()
    navigate(page, "/contacts/trial/")
    fill_trial(page)
    token = page.locator('[name="submission_token"]').input_value()
    key = signing.loads(token, salt=TOKEN_SALT)["key"]
    page.route("**/contacts/trial/", lambda route: route.fulfill(status=503, content_type="text/html", body="Local simulated server failure") if route.request.method == "POST" else route.continue_())
    page.locator("[data-submit]").click()
    expect(page.locator("[data-dynamic-errors]")).to_be_visible()
    expect(page.locator("#id_name")).to_have_value("Élodie Test")
    assert not saved_rows(key)
    page.unroute("**/contacts/trial/")

    def lost_response(route):
        if route.request.method == "POST":
            route.fetch()
            route.abort("failed")
        else:
            route.continue_()

    page.route("**/contacts/trial/", lost_response)
    page.locator("[data-submit]").click()
    expect(page.locator("[data-dynamic-errors]")).to_be_visible()
    expect(page.locator("[data-submit]")).to_be_enabled()
    assert len(saved_rows(key)) == 1
    expect(page.locator("#id_phone")).to_have_value("+442079460958")
    page.unroute("**/contacts/trial/")
    page.locator("[data-submit]").evaluate("button => {button.click();button.click();}")
    page.wait_for_url("**/contacts/trial/success/")
    assert len(saved_rows(key)) == 1
    layout(page, "success 390")
    screenshot(page, "final-success-en-390.png")
    entry = saved_rows(key)[0]
    navigate(page, "/admin/login/")
    page.locator("#id_username").fill(CREDENTIALS["admin"])
    page.locator("#id_password").fill(CREDENTIALS["password"])
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_url("**/admin/")
    navigate(page, f"/admin/contacts/contactmessage/{entry['pk']}/change/")
    expect(page.locator("#id_name")).to_have_value("Élodie Test")
    expect(page.locator("#id_direction")).to_have_value("undecided")
    expect(page.locator("#id_phone")).to_have_value("+442079460958")
    expect(page.locator("#id_preferred_contact")).to_have_value("whatsapp")
    navigate(page, "/admin/help/")
    expect(page.locator("h1").filter(has_text="Phoenix Song: работа с сайтом")).to_be_visible()
    record("503 and lost response retain input; retry/double click create one row; browser admin matches saved values")
    context.close()
    assert not errors, errors
    browser.close()

report = {"engine": "system Chromium via Playwright", "base": BASE, "checks": results, "javascript_errors": errors, "external_network_delivery": "not tested", "microphone": "not tested", "geographic_access": "not tested"}
Path("docs/phoenix-song/browser-checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print("PASS browser matrix complete", flush=True)
