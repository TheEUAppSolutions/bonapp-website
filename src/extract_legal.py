#!/usr/bin/env python3
"""Turn the archived bon-app.net legal pages into clean HTML fragments.

bon-app.net has been returning HTTP 500 for its whole WordPress install, so unlike the
euappsolutions port there is no live site to scrape. The sources in src/legal-src/ are
Wayback Machine captures (`id_` raw originals, so no archive toolbar is injected). They
are the same Astra + Elementor stack, so the same widget walker applies: the body is a
flat run of `.elementor-widget-container` divs holding headings and text blocks.

    python3 src/extract_legal.py

Writes src/legal/<slug>.html. Text is never rewritten, with one deliberate exception:
the boilerplate's "Application ... named X" slot is replaced with the token {{APP_NAME}}.
The captured pages name "Car Connect -My Smart keys" — an app this company does not
publish, copy-pasted when the policy was cloned — so build.py fills the slot with the
correct app per page instead of republishing the error.

The fragments are committed. Re-run only to re-derive them from the captures.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "legal-src"
OUT = ROOT / "src" / "legal"

PAGES = {
    "privacy-policy": "Privacy Policy",
    "term-of-use": "Term of use",
}

# the wrong app name carried over from the cloned policy, replaced with a fillable token
# the separator varies between the two pages: a hyphen on one, an &#8211; en-dash on the
# other, so match any dash form (or none) rather than a literal "-"
WRONG_APP_NAME = re.compile(
    r"(?i)\bCar\s*connect\s*(?:-|\u2013|\u2014|&#8211;|&#8212;|&ndash;|&mdash;)?\s*My\s*Smart\s*keys\b"
)

# The captured pages link to /bone-app-t-privacy-policy/ and /bone-app-t-term-of-use/.
# Neither was ever captured by the archive and neither exists now — they were broken links
# on the old site (a typo for "bon-app-t-"). Turn them into tokens that build.py resolves
# to the real pages, so the text keeps its cross-references without inventing URLs.
LINK_FIXES = {
    "/bone-app-t-privacy-policy/": "{{PRIVACY_URL}}",
    "/bone-app-t-term-of-use/": "{{TERMS_URL}}",
}

WIDGET_OPEN = re.compile(r'<div[^>]*\bclass="[^"]*\belementor-widget-container\b[^"]*"[^>]*>', re.I)
DIV_TAG = re.compile(r"(?i)<(/?)div\b[^>]*>")
HEADING = re.compile(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>")
BLOCK_START = re.compile(r"(?i)^\s*<(p|ul|ol|h[1-6]|table)\b")

FORM_LABELS = {"name", "email", "e-mail", "website", "phone", "message",
               "subject", "send", "submit", "*"}


def is_form_noise(text):
    words = re.findall(r"[\w'-]+|\*", text.lower())
    return bool(words) and all(w in FORM_LABELS for w in words)


def iter_widgets(region):
    """Yield each widget container's inner HTML, matching nested <div>s properly."""
    for opening in WIDGET_OPEN.finditer(region):
        start = opening.end()
        depth = 1
        for tag in DIV_TAG.finditer(region, start):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                yield region[start:tag.start()]
                break


def inline_only(frag):
    """Keep strong/em/a/br, drop every other tag and all attributes except href."""
    def tag(m):
        closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if name in ("strong", "b"):
            return "</strong>" if closing else "<strong>"
        if name in ("em", "i"):
            return "</em>" if closing else "<em>"
        if name == "br":
            return "<br>"
        if name == "a":
            if closing:
                return "</a>"
            href = re.search(r'href=(["\'])(.*?)\1', attrs, re.I)
            if not href:
                return ""
            url = html.escape(href.group(2), quote=True)
            # the captures rewrite outbound links through web.archive.org; unwrap them
            url = re.sub(r"^https?://web\.archive\.org/web/\d+(?:id_)?/", "", url)
            rel = ' rel="noopener"' if url.startswith("http") else ""
            return f'<a href="{url}"{rel}>'
        return " "

    frag = re.sub(r"(?is)<!--.*?-->", "", frag)
    frag = re.sub(r"(?is)<(/?)([a-z0-9]+)((?:\s[^>]*)?)/?>", tag, frag)
    return re.sub(r"\s+", " ", frag).strip()


def blocks_from(raw):
    """Paragraphs and lists out of a run of non-heading widget content."""
    out = []
    for chunk in re.split(r"(?is)(<ul.*?</ul>|<ol.*?</ol>|<table.*?</table>)", raw):
        if not chunk or not chunk.strip():
            continue
        if re.match(r"(?is)^\s*<(ul|ol)\b", chunk):
            items = [inline_only(m) for m in re.findall(r"(?is)<li[^>]*>(.*?)</li>", chunk)]
            items = [i for i in items if i]
            if items:
                kind = "ol" if chunk.lstrip().lower().startswith("<ol") else "ul"
                out.append(f"<{kind}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{kind}>")
            continue
        if re.match(r"(?is)^\s*<table\b", chunk):
            continue
        if BLOCK_START.match(chunk):
            for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", chunk):
                t = inline_only(p)
                if t:
                    out.append(f"<p>{t}</p>")
            continue
        for para in re.split(r"(?i)\n\s*\n|<br\s*/?>\s*<br\s*/?>", chunk):
            t = inline_only(para)
            if t and t != "<br>":
                out.append(f"<p>{t}</p>")
    return out


def widget_to_html(raw):
    """Walk a widget in document order; text widgets mix headings and paragraphs."""
    out = []
    for part in re.split(r"(?is)(<h[1-6][^>]*>.*?</h[1-6]>)", raw):
        if not part or not part.strip():
            continue
        h = HEADING.fullmatch(part.strip())
        if h:
            text = re.sub(r"(?is)</?a[^>]*>", "", inline_only(h.group(2))).strip()
            if text:
                level = 2 if int(h.group(1)) <= 4 else 3
                out.append(f"<h{level}>{text}</h{level}>")
            continue
        out.extend(blocks_from(part))
    return out


def extract(doc, page_title):
    start = doc.find('id="content"')
    end = doc.find("<footer", start if start > 0 else 0)
    region = doc[start if start > 0 else 0: end if end > 0 else len(doc)]
    region = re.sub(r"(?is)<(script|style|noscript|svg|nav)[^>]*>.*?</\1>", " ", region)

    blocks, seen_title = [], False
    for raw in iter_widgets(region):
        for block in widget_to_html(raw):
            plain = html.unescape(re.sub(r"(?is)<[^>]+>", "", block)).strip()
            if not plain or plain.lower() in ("skip to content", "menu", "scroll to top"):
                continue
            if block.startswith("<p>") and is_form_noise(plain):
                continue
            if not seen_title and block.startswith("<h2>") and plain.lower().rstrip("!") in (
                page_title.lower(), "privacy policy", "term of use", "terms of use",
                "terms and conditions",
            ):
                seen_title = True
                continue
            if blocks and blocks[-1] == block:
                continue  # Elementor duplicates widgets for its mobile layout
            blocks.append(block)
    return blocks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    failed = False
    for slug, title in PAGES.items():
        source = SRC / f"{slug}.html"
        if not source.exists():
            print(f"! {slug}: missing {source}", file=sys.stderr)
            failed = True
            continue
        blocks = extract(source.read_text(encoding="utf-8", errors="replace"), title)
        body = "\n".join(blocks)
        body, swapped = WRONG_APP_NAME.subn("{{APP_NAME}}", body)
        fixed = 0
        for bad, token in LINK_FIXES.items():
            body, n = re.subn(re.escape(bad), token, body)
            fixed += n
        words = len(re.sub(r"(?is)<[^>]+>", " ", body).split())
        if words < 500:
            print(f"! {slug}: only {words} words extracted, refusing to write", file=sys.stderr)
            failed = True
            continue
        (OUT / f"{slug}.html").write_text(body + "\n")
        heads = sum(1 for b in blocks if b.startswith("<h"))
        print(f"{slug}.html  {words:,} words  {len(blocks)} blocks  {heads} headings  "
              f"{swapped} app-name slot(s), {fixed} link(s) repointed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
