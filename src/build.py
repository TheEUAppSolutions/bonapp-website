#!/usr/bin/env python3
"""Generate the bon-app.net static site.

    python3 src/build.py                 # build for the custom domain (paths at /)
    python3 src/build.py --base /repo    # build for a github.io project URL

Forked from the euappsolutions-site generator; same design system and same checks.
Everything is written to the repository root so GitHub Pages can serve the branch
directly. Sources live in src/ and assets/ and are left alone.
"""
import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

SITE = "https://bon-app.net"
COMPANY = "Bon App & T"
COMPANY_LEGAL = "Bon App & T Ltd"
EMAIL = "info@bon-app.net"
ADDRESS = ["71-75 Shelton Street", "Covent Garden", "London WC2H 9JQ", "United Kingdom"]

BASE = ""

# Legal pages. The two umbrella documents keep the paths the old WordPress site used --
# Timestamp Camera's App Store listing cites /privacy-policy/ -- and each app additionally
# gets its own pair, because the boilerplate names a single "Application" and several
# listings currently point at domains the company no longer controls.
LEGAL_UMBRELLA = {
    "privacy-policy": ("Privacy Policy", "privacy-policy"),
    "term-of-use": ("Terms of Use", "term-of-use"),
}
# alias path -> the umbrella slug whose text and canonical URL it borrows
LEGAL_ALIASES = {
    "terms-of-use": "term-of-use",
    "privacy": "privacy-policy",
}

pages_built = []


# --- helpers -----------------------------------------------------------------

def e(text):
    return html.escape(str(text), quote=True)


def url(path=""):
    path = path.strip("/")
    return f"{BASE}/{path}/" if path else f"{BASE}/"


def asset(path):
    return f"{BASE}/assets/{path.lstrip('/')}"


def thousands(n):
    return f"{n:,}"


def webp_size(path):
    """(width, height) from a WebP header, so <img> carries a correct aspect ratio."""
    data = path.read_bytes()[:32]
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    kind = data[12:16]
    if kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        return (int.from_bytes(data[26:28], "little") & 0x3FFF,
                int.from_bytes(data[28:30], "little") & 0x3FFF)
    if kind == b"VP8L" and data[20:21] == b"\x2f":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":
        return (int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1)
    return None


def icon(name):
    paths = {
        "arrow": '<path d="M4 10h12m0 0-4.5-4.5M16 10l-4.5 4.5" stroke="currentColor" '
                 'stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        "apple": '<path d="M13.6 10.6c0-2 1.6-2.9 1.7-3-1-1.4-2.4-1.6-2.9-1.6-1.2-.1-2.4.7-3 .7s-1.6-.7-2.6-.7C5.5 6 4.3 6.8 3.6 8c-1.3 2.3-.3 5.7 1 7.6.6.9 1.4 1.9 2.4 1.9s1.3-.6 2.5-.6 1.5.6 2.6.6 1.7-.9 2.3-1.8c.7-1 1-2 1-2.1s-2-.8-2-3zM11.7 4.7c.5-.7.9-1.6.8-2.5-.8 0-1.8.5-2.4 1.2-.5.6-1 1.6-.8 2.5.9.1 1.8-.4 2.4-1.2z" fill="currentColor"/>',
        "sun": '<circle cx="8" cy="8" r="3.2" fill="currentColor"/><path d="M8 .8v1.8M8 13.4v1.8M15.2 8h-1.8M2.6 8H.8M13.1 2.9l-1.3 1.3M4.2 11.8l-1.3 1.3M13.1 13.1l-1.3-1.3M4.2 4.2 2.9 2.9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
        "moon": '<path d="M14 9.8A6.2 6.2 0 0 1 6.2 2 6.4 6.4 0 1 0 14 9.8z" fill="currentColor"/>',
    }
    box = "0 0 20 20" if name == "arrow" else "0 0 16 16"
    return f'<svg viewBox="{box}" aria-hidden="true" focusable="false">{paths[name]}</svg>'


def mark():
    return (
        '<svg class="brand__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
        '<defs><linearGradient id="m" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#34D399"/><stop offset="1" stop-color="#047857"/>'
        '</linearGradient></defs>'
        '<rect width="32" height="32" rx="8.5" fill="url(#m)"/>'
        '<path d="M11 10.5h6.5a3.3 3.3 0 0 1 0 6.6H11zM11 17.1h7.4a3.3 3.3 0 0 1 0 6.6H11z" '
        'fill="#fff" opacity=".96"/>'
        '<path d="M11 8.4v15.3" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>'
        '</svg>'
    )


# --- chrome ------------------------------------------------------------------

def head(title, description, path, *, image=None, jsonld=None, noindex=False,
         canonical_path=None):
    path = canonical_path if canonical_path is not None else path
    canonical = SITE + url(path).replace(BASE, "", 1) if BASE else SITE + url(path)
    image = image or (SITE + asset("img/og.png").replace(BASE, "", 1) if BASE
                      else SITE + asset("img/og.png"))
    ld = f'\n<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    robots = '\n<meta name="robots" content="noindex,follow">' if noindex else ""
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">{robots}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(COMPANY)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0a0a0c" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{asset('img/mark.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{asset('img/apple-touch-icon.png')}">
<link rel="stylesheet" href="{asset('css/site.css')}">
<script>
// set the stored theme before first paint so the page never flashes the wrong palette
try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')
document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}
</script>
<noscript><style>.reveal{{opacity:1;transform:none}}</style></noscript>{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
"""


def masthead(current):
    links = [("Apps", "apps"), ("Legal", "legal"), ("Contact", "contact")]
    nav = "".join(
        '<a href="{}"{}>{}</a>'.format(
            url(slug), ' aria-current="page"' if current == slug else "", label)
        for label, slug in links
    )
    return f"""<header class="masthead">
<div class="wrap masthead__inner">
<a class="brand" href="{url()}" aria-label="{e(COMPANY)} — home">
{mark()}
<span class="brand__text">Bon App <span>&amp; T</span></span>
</a>
<nav class="nav" aria-label="Main">{nav}</nav>
<button class="theme-toggle" type="button" aria-label="Switch theme">
<span class="icon-light">{icon('sun')}</span><span class="icon-dark">{icon('moon')}</span>
</button>
</div>
</header>
<main id="main">
"""


def footer(apps):
    app_links = "".join(
        f'<li><a href="{url("apps/" + a["slug"])}">{e(a["name"])}</a></li>' for a in apps
    )
    return f"""</main>
<footer class="footer">
<div class="wrap">
<div class="footer__grid">
<div class="footer__about">
<a class="brand" href="{url()}">{mark()}<span class="brand__text">Bon App <span>&amp; T</span></span></a>
<p>A UK company publishing apps for iPhone and iPad.
{len(apps)} live on the App Store.</p>
</div>
<div class="footer__col">
<h4>Apps</h4>
<ul>{app_links}</ul>
</div>
<div class="footer__col">
<h4>Company</h4>
<ul>
<li><a href="{url('about')}">About</a></li>
<li><a href="{url('contact')}">Contact</a></li>
<li><a href="mailto:{EMAIL}">{EMAIL}</a></li>
</ul>
</div>
<div class="footer__col">
<h4>Legal</h4>
<ul>
<li><a href="{url('privacy-policy')}">Privacy Policy</a></li>
<li><a href="{url('term-of-use')}">Terms of Use</a></li>
<li><a href="{url('legal')}">Per-app policies</a></li>
</ul>
</div>
</div>
<div class="footer__base">
<span>&copy; {date.today().year} {e(COMPANY_LEGAL)}</span>
<span>{e(', '.join(ADDRESS))}</span>
</div>
</div>
</footer>
<script src="{asset('js/site.js')}" defer></script>
</body>
</html>
"""


# --- components --------------------------------------------------------------

def rating_bit(app):
    if not app["rating"]:
        return f'<span>{e(app["category"])}</span>'
    return (
        f'<span class="rating"><svg viewBox="0 0 16 16" aria-hidden="true">'
        f'<path d="M8 1.3l2 4.1 4.5.7-3.3 3.2.8 4.5L8 11.6l-4 2.1.8-4.5L1.5 6.1l4.5-.7z"/>'
        f'</svg>{app["rating"]:.1f}</span>'
        f'<span class="dot"></span><span>{thousands(app["ratingCount"])} ratings</span>'
        f'<span class="dot"></span><span>{e(app["category"])}</span>'
    )


def app_card(app):
    return f"""<a class="app-card" href="{url('apps/' + app['slug'])}">
<img class="app-card__icon" src="{asset('img/icons/' + app['slug'] + '.webp')}"
 alt="" width="58" height="58" loading="lazy" decoding="async">
<span class="app-card__body">
<span class="app-card__name">{e(app['name'])}</span>
<span class="app-card__tag">{e(app['tagline'])}</span>
<span class="app-card__meta">{rating_bit(app)}</span>
</span>
</a>"""


def app_grid(apps):
    # only five apps, so no filter bar -- every one fits on screen at once
    return ('<div class="app-grid">\n' + "\n".join(app_card(a) for a in apps) + "\n</div>")


def store_button(app, label="View on the App Store"):
    return (f'<a class="btn btn--primary" href="{e(app["storeUrl"])}" rel="noopener">'
            f'{icon("apple")}{label}</a>')


def fill(body, app_name):
    """Resolve the tokens src/extract_legal.py leaves in the legal fragments."""
    return (body
            .replace("{{APP_NAME}}", e(app_name))
            .replace("{{PRIVACY_URL}}", url("privacy-policy"))
            .replace("{{TERMS_URL}}", url("term-of-use")))


# --- pages -------------------------------------------------------------------

def write(path, content):
    out = ROOT / "index.html" if path == "" else ROOT / (
        path if path.endswith((".html", ".xml", ".txt")) else f"{path}/index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    pages_built.append(str(out.relative_to(ROOT)))


def page_home(apps, totals):
    top = apps[0]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": COMPANY_LEGAL,
        "alternateName": COMPANY,
        "url": SITE + "/",
        "email": EMAIL,
        "logo": SITE + "/assets/img/mark.svg",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "71-75 Shelton Street, Covent Garden",
            "addressLocality": "London",
            "postalCode": "WC2H 9JQ",
            "addressCountry": "GB",
        },
    }
    return head(
        f"{COMPANY} — apps for iPhone and iPad",
        f"{COMPANY_LEGAL} publishes {totals['count']} apps on the App Store, "
        f"with {thousands(totals['ratings'])} ratings and a {totals['avg']:.1f} average.",
        "", jsonld=jsonld,
    ) + masthead("") + f"""
<section class="hero">
<div class="wrap hero__grid">
<p class="eyebrow">London &middot; Apps for iPhone and iPad</p>
<h1>Five apps.<em>Forty thousand ratings.</em></h1>
<p class="lede">{COMPANY_LEGAL} publishes {totals['count']} apps on the App Store, rated
{totals['avg']:.1f} on average across {thousands(totals['ratings'])} ratings — most of
them for {e(top['name'])}, which has been picking who goes first since long before
anyone called it a trend.</p>
<div class="btn-row">
<a class="btn btn--primary" href="{url('apps')}">See the apps {icon('arrow')}</a>
<a class="btn btn--ghost" href="{url('contact')}">Get in touch</a>
</div>
<div class="stats">
<div class="stat"><span class="stat__num">{totals['count']}</span>
<span class="stat__label">Apps live</span></div>
<div class="stat"><span class="stat__num">{thousands(totals['ratings'])}</span>
<span class="stat__label">Ratings</span></div>
<div class="stat"><span class="stat__num">{totals['avg']:.2f}</span>
<span class="stat__label">Average score</span></div>
<div class="stat"><span class="stat__num">{totals['categories']}</span>
<span class="stat__label">Categories</span></div>
</div>
</div>
</section>

<section class="section section--sub" id="apps">
<div class="wrap">
<div class="section-head reveal">
<p class="eyebrow">The apps</p>
<h2>Everything we publish</h2>
<p class="lede">All {totals['count']} are live on the App Store. Ratings come straight
from Apple and are refreshed whenever the site is rebuilt.</p>
</div>
<div class="reveal">
{app_grid(apps)}
</div>
</div>
</section>

<section class="section section--tight">
<div class="wrap">
<div class="callout reveal">
<div class="callout__text">
<h2>Need help with one of these?</h2>
<p>Tell us which app you're writing about and we'll get to it faster. Every app's
privacy policy and terms live on this site.</p>
</div>
<div class="btn-row">
<a class="btn btn--primary" href="mailto:{EMAIL}">Email support</a>
<a class="btn btn--ghost" href="{url('legal')}">Legal {icon('arrow')}</a>
</div>
</div>
</div>
</section>
""" + footer(apps)


def page_apps(apps, totals):
    return head(
        f"Apps — {COMPANY}",
        f"All {totals['count']} apps published by {COMPANY_LEGAL} on the App Store.",
        "apps",
    ) + masthead("apps") + f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">{totals['count']} apps &middot; {thousands(totals['ratings'])} ratings</p>
<h1>Apps</h1>
<p class="lede">Everything we currently publish on the App Store. All free to download.</p>
</div>
{app_grid(apps)}
</div>
</section>
""" + footer(apps)


def page_app(app, apps):
    shot_dir = ROOT / "assets" / "img" / "shots" / app["slug"]
    shots = sorted(shot_dir.glob("*.webp"), key=lambda p: int(p.stem)) if shot_dir.exists() else []
    shots_html = ""
    if shots:
        def shot_img(i, s):
            size = webp_size(s)
            dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
            return (f'<img src="{asset("img/shots/" + app["slug"] + "/" + s.name)}"'
                    f' alt="{e(app["name"])} screenshot {i + 1}" loading="lazy"'
                    f' decoding="async"{dims}>')
        shots_html = f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head"><p class="eyebrow">Screenshots</p></div>
<div class="shots">{"".join(shot_img(i, s) for i, s in enumerate(shots))}</div>
</div>
</section>"""

    facts = [("Category", app["category"]), ("Price", app["price"] or "Free")]
    if app["rating"]:
        facts.append(("Rating", f'{app["rating"]:.1f} from {thousands(app["ratingCount"])}'))
    if app["languages"]:
        facts.append(("Languages", str(app["languages"])))
    if app["age"]:
        facts.append(("Age rating", app["age"]))
    if app["updated"]:
        facts.append(("Last updated", app["updated"]))
    facts_html = "".join(
        f'<div class="fact"><div class="fact__label">{e(k)}</div>'
        f'<div class="fact__value">{e(v)}</div></div>' for k, v in facts
    )

    others = [a for a in apps if a["slug"] != app["slug"]][:3]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": app["storeName"],
        "alternateName": app["name"],
        "operatingSystem": "iOS",
        "applicationCategory": app["category"],
        "url": app["storeUrl"],
        "description": app["tagline"],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "publisher": {"@type": "Organization", "name": COMPANY_LEGAL},
    }
    if app["rating"] and app["ratingCount"]:
        jsonld["aggregateRating"] = {
            "@type": "AggregateRating", "ratingValue": round(app["rating"], 2),
            "ratingCount": app["ratingCount"], "bestRating": 5, "worstRating": 1,
        }

    return head(
        f"{app['name']} — {COMPANY}", app["tagline"], f"apps/{app['slug']}",
        image=SITE + f"/assets/img/icons/{app['slug']}@512.png", jsonld=jsonld,
    ) + masthead("apps") + f"""
<section class="app-hero">
<div class="wrap">
<p class="eyebrow" style="margin-bottom:26px">
<a href="{url('apps')}">Apps</a> &nbsp;/&nbsp; {e(app['name'])}</p>
<div class="app-hero__top">
<img class="app-hero__icon" src="{asset('img/icons/' + app['slug'] + '.webp')}"
 alt="{e(app['name'])} app icon" width="116" height="116" fetchpriority="high">
<div class="app-hero__head">
<h1>{e(app['name'])}</h1>
<p class="app-hero__tag">{e(app['tagline'])}</p>
<div class="btn-row">{store_button(app)}</div>
</div>
</div>
<div class="facts">{facts_html}</div>
</div>
</section>

<section class="section section--tight">
<div class="wrap">
<div class="prose">
<p class="lede">{e(app['blurb'])}</p>
<p><a class="arrow-link" href="{url('legal/' + app['slug'] + '/privacy')}">
Privacy policy for {e(app['name'])} {icon('arrow')}</a></p>
</div>
</div>
</section>
{shots_html}
<section class="section section--sub">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">More from us</p>
<h2>Other apps</h2>
</div>
<div class="app-grid">
{chr(10).join(app_card(a) for a in others)}
</div>
</div>
</section>
""" + footer(apps)


def page_about(apps, totals):
    cats = sorted({a["category"] for a in apps})
    top = apps[0]
    return head(
        f"About — {COMPANY}",
        f"{COMPANY_LEGAL} is a UK company publishing apps for iPhone and iPad.",
        "about",
    ) + masthead("") + f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">About</p>
<h1>Who we are</h1>
</div>
<div class="prose">
<p class="lede">{e(COMPANY_LEGAL)} is a UK-registered company that builds and publishes
apps for iPhone and iPad. {totals['count']} are live on the App Store, carrying
{thousands(totals['ratings'])} ratings at a {totals['avg']:.2f} average.</p>

<h2>What we make</h2>
<p>Small, single-purpose apps across {len(cats)} App Store categories &mdash;
{e(', '.join(cats[:-1]))} and {e(cats[-1])}. A finger chooser that settles who goes
first. A camera that burns the date, time and GPS position onto the frame. An invoice
builder. A note taker. A song generator.</p>
<p>{e(top['name'])} carries most of the weight: {thousands(top['ratingCount'])} of those
ratings are its, from people who mostly needed to decide whose turn it was.</p>

<h2>Support and legal</h2>
<p>Every app is supported from one address. Email
<a href="mailto:{EMAIL}">{EMAIL}</a> and say which app you mean.</p>
<p>Each app's privacy policy and terms are published here rather than on a third-party
host, so the links in our App Store listings keep working. See
<a href="{url('legal')}">the legal index</a>.</p>
</div>

<div class="legal-meta">
<span>{e(COMPANY_LEGAL)}</span>
<span>{e(', '.join(ADDRESS))}</span>
</div>
</div>
</section>
""" + footer(apps)


def page_contact(apps):
    address = "<br>".join(e(line) for line in ADDRESS)
    return head(
        f"Contact — {COMPANY}", f"Get in touch with {COMPANY_LEGAL}: {EMAIL}.", "contact",
    ) + masthead("contact") + f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">Contact</p>
<h1>Get in touch</h1>
<p class="lede">One inbox for everything &mdash; app support, privacy questions and new
work. Tell us which app you're writing about and we'll get to it faster.</p>
</div>
<div class="cols">
<dl class="contact-list">
<div class="contact-item"><dt>Email</dt>
<dd><a href="mailto:{EMAIL}">{EMAIL}</a></dd></div>
<div class="contact-item"><dt>Legal</dt>
<dd><a href="{url('privacy-policy')}">Privacy Policy</a> &middot;
<a href="{url('term-of-use')}">Terms of Use</a> &middot;
<a href="{url('legal')}">Per-app</a></dd></div>
</dl>
<dl class="contact-list">
<div class="contact-item"><dt>Registered office</dt>
<dd><address>{e(COMPANY_LEGAL)}<br>{address}</address></dd></div>
</dl>
</div>
</div>
</section>
""" + footer(apps)


def page_legal_index(apps):
    rows = "".join(
        f'<div class="app-card" style="align-items:center">'
        f'<img class="app-card__icon" src="{asset("img/icons/" + a["slug"] + ".webp")}"'
        f' alt="" width="58" height="58" loading="lazy">'
        f'<span class="app-card__body"><span class="app-card__name">{e(a["name"])}</span>'
        f'<span class="app-card__meta">'
        f'<a class="arrow-link" href="{url("legal/" + a["slug"] + "/privacy")}">Privacy</a>'
        f'<span class="dot"></span>'
        f'<a class="arrow-link" href="{url("legal/" + a["slug"] + "/terms")}">Terms</a>'
        f'</span></span></div>' for a in apps
    )
    return head(
        f"Legal — {COMPANY}",
        f"Privacy policies and terms of use for every app published by {COMPANY_LEGAL}.",
        "legal",
    ) + masthead("legal") + f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">Legal</p>
<h1>Policies</h1>
<p class="lede">The company-wide documents, plus a copy for each app naming that app
specifically &mdash; these are the URLs our App Store listings point at.</p>
</div>
<div class="prose" style="margin-bottom:34px">
<p><a class="arrow-link" href="{url('privacy-policy')}">Privacy Policy {icon('arrow')}</a></p>
<p><a class="arrow-link" href="{url('term-of-use')}">Terms of Use {icon('arrow')}</a></p>
</div>
<div class="section-head"><p class="eyebrow">Per app</p></div>
<div class="app-grid">{rows}</div>
</div>
</section>
""" + footer(apps)


def page_legal(slug, title, body, apps, *, canonical_path=None, subtitle=None):
    note = f'<p class="lede">{e(subtitle)}</p>' if subtitle else ""
    return head(
        f"{title} — {COMPANY}",
        f"{title} for {COMPANY_LEGAL}" + (f", covering {subtitle}." if subtitle
                                          else f", {', '.join(ADDRESS)}."),
        slug, canonical_path=canonical_path,
    ) + masthead("legal") + f"""
<section class="section section--tight">
<div class="wrap">
<div class="section-head">
<p class="eyebrow">Legal</p>
<h1>{e(title)}</h1>
{note}
</div>
<div class="prose">
{body}
</div>
<div class="legal-meta">
<span>{e(COMPANY_LEGAL)}</span>
<span>{e(', '.join(ADDRESS))}</span>
<span><a href="mailto:{EMAIL}">{EMAIL}</a></span>
</div>
</div>
</section>
""" + footer(apps)


def page_404(apps):
    return head("Page not found — " + COMPANY,
                f"That page doesn't exist. See the {len(apps)} apps {COMPANY_LEGAL} "
                f"publishes, or get in touch.", "404", noindex=True) + masthead("") + f"""
<section class="section">
<div class="wrap center-page">
<p class="eyebrow">Error 404</p>
<h1>This page doesn't exist</h1>
<p class="lede">The link may be out of date. Everything we publish is on the apps page.</p>
<div class="btn-row">
<a class="btn btn--primary" href="{url('apps')}">See the apps {icon('arrow')}</a>
<a class="btn btn--ghost" href="{url()}">Home</a>
</div>
</div>
</section>
""" + footer(apps)


# --- build -------------------------------------------------------------------

def main():
    global BASE
    if "--base" in sys.argv:
        BASE = "/" + sys.argv[sys.argv.index("--base") + 1].strip("/")

    apps = json.loads((SRC / "apps.json").read_text())
    ratings = sum(a["ratingCount"] for a in apps)
    totals = {
        "count": len(apps),
        "ratings": ratings,
        "avg": sum((a["rating"] or 0) * a["ratingCount"] for a in apps) / ratings,
        "categories": len({a["category"] for a in apps}),
    }

    write("", page_home(apps, totals))
    write("apps", page_apps(apps, totals))
    for app in apps:
        write(f"apps/{app['slug']}", page_app(app, apps))
    write("about", page_about(apps, totals))
    write("contact", page_contact(apps))
    write("legal", page_legal_index(apps))

    bodies = {s: (SRC / "legal" / f"{s}.html").read_text() for s in LEGAL_UMBRELLA}
    # the clean product names, not storeName: App Store titles carry ASO junk
    # ("Invoice Maker | ^Generator") that has no place in a legal document
    all_names = ", ".join(a["name"] for a in apps)

    # umbrella documents: the app-name slot names every app the company publishes
    for slug, (title, source) in LEGAL_UMBRELLA.items():
        write(slug, page_legal(slug, title, fill(bodies[source], all_names), apps))

    # paths the old site also answered on, kept so nothing 404s
    for alias, target in LEGAL_ALIASES.items():
        title = LEGAL_UMBRELLA[target][0]
        write(alias, page_legal(alias, title, fill(bodies[target], all_names), apps,
                                canonical_path=target))

    # one pair per app, naming that app -- these are the URLs to put in App Store Connect
    for app in apps:
        for kind, source, title in (("privacy", "privacy-policy", "Privacy Policy"),
                                    ("terms", "term-of-use", "Terms of Use")):
            write(f"legal/{app['slug']}/{kind}",
                  page_legal(f"legal/{app['slug']}/{kind}", f"{title} — {app['name']}",
                             fill(bodies[source], app["name"]), apps,
                             subtitle=app["storeName"]))

    write("404.html", page_404(apps))

    urls = ([""] + ["apps", "about", "contact", "legal"]
            + [f"apps/{a['slug']}" for a in apps] + list(LEGAL_UMBRELLA)
            + [f"legal/{a['slug']}/{k}" for a in apps for k in ("privacy", "terms")])
    today = date.today().isoformat()
    entries = "\n".join(
        f"  <url><loc>{SITE}/{(p + '/') if p else ''}</loc>"
        f"<lastmod>{today}</lastmod>"
        f"<priority>{'1.0' if not p else '0.8' if p == 'apps' else '0.6'}</priority></url>"
        for p in urls
    )
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f"{entries}\n</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")

    (ROOT / "CNAME").write_text("bon-app.net\n")
    (ROOT / ".nojekyll").write_text("")

    print(f"built {len(pages_built)} files")


if __name__ == "__main__":
    main()
