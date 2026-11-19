import json
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.html import parse_html
from django.urls import reverse

from contacts.models import ContactMessage


SOURCE = json.loads((Path(__file__).resolve().parents[1] / "docs/phoenix-song/author-copy-v2.json").read_text())["blocks"]


def descendants(node):
    for child in getattr(node, "children", []):
        if not isinstance(child, str):
            yield child
            yield from descendants(child)


def select(root, selector):
    nodes = [root]
    direct = False
    for part in selector.split():
        if part == ">":
            direct = True
            continue
        first = part.endswith(":first-of-type")
        part = part.removesuffix(":first-of-type")
        selected = []
        for node in nodes:
            matches = []
            for candidate in (node.children if direct else descendants(node)):
                if isinstance(candidate, str):
                    continue
                attrs = dict(candidate.attributes)
                if part.startswith("."):
                    match = part[1:] in attrs.get("class", "").split()
                elif part.startswith("#"):
                    match = attrs.get("id") == part[1:]
                elif "[" in part:
                    tag, attribute = part.rstrip("]").split("[", 1)
                    key, separator, value = attribute.partition("=")
                    match = (not tag or candidate.name == tag) and key in attrs and (not separator or attrs[key] == value)
                else:
                    match = candidate.name == part
                if match:
                    matches.append(candidate)
            selected.extend(matches[:1] if first else matches)
        nodes = selected
        direct = False
    return nodes


def visible_text(node):
    if isinstance(node, str):
        return node
    if dict(node.attributes).get("aria-hidden") == "true":
        return ""
    if node.name == "br":
        return " "
    return " ".join(visible_text(child) for child in node.children)


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


class AuthorCopyTests(TestCase):
    def check_field(self, root, selector, expected):
        matches = select(root, selector)
        self.assertEqual(len(matches), 1, selector)
        self.assertEqual(normalize(visible_text(matches[0])), normalize(expected), selector)
        return matches[0]

    def test_all_31_author_fields_and_separate_ordered_paragraphs(self):
        self.client.cookies["phoenix_songs_language"] = "ru"
        home = parse_html(self.client.get("/").content.decode())
        checked = 0
        for block in list(SOURCE.values())[:7]:
            for selector, expected in block["fields"].items():
                target = f'{block["selector"]} {selector}'
                with self.subTest(selector=target):
                    element = self.check_field(home, target, " ".join(expected) if isinstance(expected, list) else expected)
                    if isinstance(expected, list):
                        paragraphs = select(element, "p")
                        self.assertEqual(len(paragraphs), len(expected))
                        self.assertEqual([normalize(visible_text(paragraph)) for paragraph in paragraphs], expected)
                        self.assertTrue(all(paragraph in element.children for paragraph in paragraphs))
                    checked += 1
        page = self.client.get(reverse("contacts:trial"))
        payload = {"name": "Élodie Müller", "phone": "+33142345678", "direction": "undecided", "preferred_contact": "other", "other_contact": "test@example.com", "submission_token": page.context["form"].initial["submission_token"]}
        conditional = self.client.post(reverse("contacts:trial"), {**payload, "name": ""})
        self.assertFalse(conditional.context["form"].fields["other_contact"].disabled)
        form = parse_html(conditional.content.decode())
        saved = self.client.post(reverse("contacts:trial"), payload, follow=True)
        self.assertEqual(ContactMessage.objects.count(), 1)
        success = parse_html(saved.content.decode())
        for selector, expected in SOURCE["A8"]["fields"].items():
            with self.subTest(selector=selector):
                root = success if selector.startswith(".success-card") else form
                self.check_field(root, selector, expected)
                checked += 1
        self.client.cookies["phoenix_songs_language"] = "en"
        blog = parse_html(self.client.get("/journal/").content.decode())
        for selector, expected in SOURCE["A9"]["fields"].items():
            self.check_field(blog, selector, expected)
            checked += 1
        self.assertEqual(checked, 31)

    def test_english_preserves_paragraph_structure_and_first_person_details(self):
        response = self.client.get("/")
        home = parse_html(response.content.decode())
        for block in list(SOURCE.values())[:7]:
            paragraphs = select(home, f'{block["selector"]} .body-copy p')
            self.assertEqual(len(paragraphs), len(block["fields"][".body-copy"]))
        for detail in ["Together with my team", "classical music education", "Viktor Tsoi", "Vladimir Vysotsky", "Brother 2…", "USA, Germany, Italy, Australia", "source of inspiration, freedom and new discoveries"]:
            self.assertContains(response, detail)

    def test_admin_uses_blog_labels(self):
        admin = get_user_model().objects.create_superuser("copy-admin", "admin@example.com", "Synthetic-194!")
        self.client.force_login(admin)
        page = self.client.get(reverse("admin:journal_article_add"))
        for old_label in ["Музыкальный журнал", "Статьи журнала", "Показывать в журнале"]:
            self.assertNotContains(page, old_label)
        for label in ["Наш блог", "Статьи блога", "Показывать в блоге"]:
            self.assertContains(page, label)
