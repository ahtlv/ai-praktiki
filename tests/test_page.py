import pathlib
import re
import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")

HERO_TEXT = "Здравствуйте! Я с сайта ИИ-практиков. Хочу автоматизировать процесс в бизнесе: "
CTA_TEXT = "Здравствуйте! Я с сайта ИИ-практиков. Первым хочу отдать ИИ такой процесс: "


def section_html(section_id):
    match = re.search(r'<section id="%s"[^>]*>.*?</section>' % re.escape(section_id), HTML, re.S)
    assert match, "section #%s not found" % section_id
    return match.group(0)


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "title"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script", "title"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def text_of(html):
    parser = _TextParser()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


class _TagParser(HTMLParser):
    def __init__(self, tag):
        super().__init__()
        self.tag = tag
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag == self.tag:
            self.found.append(dict(attrs))


def tags(html, tag):
    parser = _TagParser(tag)
    parser.feed(html)
    return parser.found


def links(html):
    return tags(html, "a")


def link_text(html, href):
    match = re.search(r'<a[^>]*href="%s"[^>]*>(.*?)</a>' % re.escape(href), html, re.S)
    return text_of(match.group(1)) if match else None


def tg_text(href):
    parts = urlsplit(href)
    return parts.netloc, parts.path, parse_qs(parts.query, keep_blank_values=True).get("text", [None])[0]


def css():
    return re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)


def css_var(name):
    root = re.search(r":root\s*\{(.*?)\}", css(), re.S).group(1)
    return re.search(r"%s\s*:\s*([^;]+);" % re.escape(name), root).group(1).strip()


def _luminance(hex_color):
    channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(fg, bg):
    light, dark = sorted([_luminance(fg), _luminance(bg)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


class PageTests(unittest.TestCase):
    def test_head(self):
        self.assertRegex(HTML, r"(?i)^<!doctype html>")
        self.assertIn('<html lang="ru">', HTML)
        self.assertIn('<meta charset="utf-8">', HTML)
        self.assertIn('content="width=device-width, initial-scale=1"', HTML)
        self.assertRegex(HTML, r"<title>[^<]+</title>")
        self.assertRegex(HTML, r'<meta name="description" content="[^"]+">')

    def test_no_external_resources(self):
        for forbidden in ("<script", 'rel="stylesheet"', "@import", "url("):
            self.assertNotIn(forbidden, HTML)
        self.assertEqual(HTML.count("<style>"), 1)
        for a in links(HTML):
            self.assertTrue(a["href"].startswith(("https://t.me/ahtlv", "#")), a["href"])
        for tag in ("img", "source", "iframe", "video", "audio"):
            for el in tags(HTML, tag):
                self.assertEqual(el.get("src"), "portrait.png")

    def test_sections_order(self):
        ids = [s.get("id") for s in tags(HTML, "section")]
        self.assertEqual(ids, ["hero", "problem", "how", "about", "cta"])

    def test_palette(self):
        expected = {
            "--bg": "#FAF6F0", "--bg-alt": "#F1E7DA", "--line": "#E8DFD3",
            "--text": "#2B2622", "--muted": "#5C534C",
            "--accent": "#B4532A", "--accent-ink": "#9A4420",
        }
        for name, value in expected.items():
            self.assertEqual(css_var(name).upper(), value, name)

    def test_palette_contrast(self):
        v = css_var
        self.assertGreaterEqual(contrast("#FFFFFF", v("--accent")), 4.5)
        self.assertGreaterEqual(contrast(v("--muted"), v("--bg")), 4.5)
        self.assertGreaterEqual(contrast(v("--accent"), v("--bg")), 4.5)
        self.assertGreaterEqual(contrast(v("--accent-ink"), v("--bg-alt")), 4.5)
        self.assertGreaterEqual(contrast("#FFFFFF", v("--accent-ink")), 4.5)

    def test_wrapping_rules(self):
        self.assertRegex(css(), r"overflow-wrap:\s*(break-word|anywhere)")
        self.assertRegex(css(), r"max-width:\s*680px")

    def test_about_text_can_shrink(self):
        # при крупном системном шрифте длинные слова распирают блок рядом с портретом:
        # в строке его держит min-width: 0, в колонке на телефоне — align-items: stretch
        self.assertRegex(css(), r"\.about\s*>\s*div\s*\{[^}]*min-width:\s*0")
        mobile = re.search(r"@media \(max-width: 600px\)\s*\{(.*)\}", css(), re.S).group(1)
        self.assertRegex(mobile, r"\.about\s*\{[^}]*align-items:\s*stretch")

    def test_focus_visible(self):
        self.assertRegex(css(), r"\.btn:focus-visible\s*\{[^}]*outline")

    def test_hero_copy(self):
        hero = section_html("hero")
        text = text_of(hero)
        self.assertIn("ИИ-практики из Беларуси", text)
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", HTML, re.S)
        self.assertEqual(len(h1s), 1)
        self.assertIn(h1s[0], hero)
        h1 = text_of(h1s[0])
        self.assertIn("автоматизирует", h1)
        self.assertIn("процесс", h1)
        self.assertIn("белорусск", text.lower())
        self.assertNotIn("Claude Code", text)
        self.assertNotIn("трансформац", text.lower())

    def test_hero_button(self):
        hero = section_html("hero")
        buttons = [a for a in links(hero) if "btn" in a.get("class", "").split()]
        self.assertEqual(len(buttons), 1)
        href = buttons[0]["href"]
        self.assertEqual(link_text(hero, href), "Написать в Telegram")
        self.assertEqual(tg_text(href), ("t.me", "/ahtlv", HERO_TEXT))

    def test_problem_block(self):
        problem = section_html("problem")
        text = text_of(problem)
        self.assertIn("Сейчас", text)
        self.assertIn("С нами", text)
        self.assertIn("рынок молодой", text.lower())
        self.assertIn("белорусск", text.lower())
        self.assertIn("<h2", problem)

    def test_how_steps(self):
        how = section_html("how")
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", how, re.S)
        self.assertIn("Как работаем", text_of(h2.group(1)))
        lists = re.findall(r'<ol class="steps">(.*?)</ol>', how, re.S)
        self.assertEqual(len(lists), 1)
        items = [text_of(li) for li in re.findall(r"<li>(.*?)</li>", lists[0], re.S)]
        self.assertEqual(len(items), 3)
        self.assertIn("процесс", items[0])
        self.assertIn("подберём", items[1])
        self.assertIn("автоматизирует", items[2])

    def test_examples(self):
        found = re.findall(r'<p class="examples">(.*?)</p>', HTML, re.S)
        self.assertEqual(len(found), 1)
        self.assertEqual(text_of(found[0]), "Например: обработка заявок, отчёты, ответы клиентам")

    def test_portrait(self):
        path = ROOT / "portrait.png"
        self.assertTrue(path.exists())
        data = path.read_bytes()
        self.assertLessEqual(len(data), 150_000)
        self.assertEqual(int.from_bytes(data[16:20], "big"), 480)
        self.assertEqual(int.from_bytes(data[20:24], "big"), 480)
        imgs = tags(section_html("about"), "img")
        self.assertEqual(len(imgs), 1)
        img = imgs[0]
        self.assertEqual(img.get("src"), "portrait.png")
        self.assertEqual(img.get("alt"), "Анатоль Хотулёв")
        self.assertEqual(img.get("width"), "140")
        self.assertEqual(img.get("height"), "140")
        self.assertIn("portrait", img.get("class", "").split())

    def test_about_facts(self):
        text = text_of(section_html("about"))
        for fact in ("Анатоль Хотулёв", "Claude Code", "70+", "Web3 Belarus", "2 500+", "15+"):
            self.assertIn(fact, text)

    def test_cta_button(self):
        cta = section_html("cta")
        self.assertIn("Какой процесс вы бы отдали ИИ первым?", text_of(cta))
        cta_links = links(cta)
        self.assertEqual(len(cta_links), 1)
        classes = cta_links[0].get("class", "").split()
        self.assertIn("btn", classes)
        self.assertIn("btn--wide", classes)
        href = cta_links[0]["href"]
        self.assertEqual(link_text(cta, href), "Написать в Telegram")
        self.assertEqual(tg_text(href), ("t.me", "/ahtlv", CTA_TEXT))

    def test_two_buttons_differ(self):
        tg = [a["href"] for a in links(HTML) if a["href"].startswith("https://t.me/")]
        self.assertEqual(len(tg), 2)
        self.assertNotEqual(tg_text(tg[0])[2], tg_text(tg[1])[2])

    def test_no_fabrication(self):
        text = text_of(HTML).lower()
        for word in ("отзыв", "кейс", "₽", "руб", "byn", "$", "трансформац", "llm", "промпт", "агент"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
