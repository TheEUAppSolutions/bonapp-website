#!/usr/bin/env python3
"""Merge the curated per-app copy below with live App Store metadata into src/apps.json.

Same split as the euappsolutions-site generator this was forked from: the editorial half
(display name, tagline, blurb, slug) lives here; the numbers, artwork and categories come
from the iTunes lookup API so re-running keeps the site honest.

    python3 src/make_apps_json.py            # refresh from the App Store
    python3 src/make_apps_json.py --offline  # reuse src/appstore-raw.json

Only apps whose App Store sellerName is SELLER are included. That check matters here:
several apps built on this Apple team are published under other sellers, and one app
sharing the "funkymonkeyapps" bundle prefix (AI Chatbot) belongs to a different seller
entirely, so a wrong bundle ID fails loudly instead of publishing someone else's app.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELLER = "BON APP & T LTD"

# slug, bundleId, display name, tagline, blurb
CURATED = [
    (
        "chooser", "nanotube.chooser", "Chooser!",
        "Everyone puts a finger on the screen. It picks who goes first.",
        "The original finger chooser. Everyone holds a finger on the screen, and it picks "
        "one at random — for board games, card games, parties and every argument about who "
        "goes first. Nearly 40,000 people have rated it.",
    ),
    (
        "ai-music", "com.funkymonkeyapps.AIMusic", "AI Music",
        "Describe a song and get a finished track back, vocals and all.",
        "Say what you want to hear — a feeling, a story, a moment — and pick a genre. It "
        "writes the lyrics, sings them, produces the track and designs the cover art.",
    ),
    (
        "invoice-maker", "com.bonappt.invoicemaker", "Invoice Maker",
        "Invoices, estimates and payments for a small business.",
        "Build invoices from a set of templates, add your own logo and company details, and "
        "take payment inside the app. Doubles as a simple point of sale.",
    ),
    (
        "timestamp-camera", "com.bonapp.timestamp", "Timestamp Camera",
        "Burns the date, time and GPS location straight onto the photo.",
        "Photos and video stamped with the real date, time, GPS address and your own "
        "watermark as you shoot, rather than edited on afterwards. Built for site work, "
        "inspections and anything that has to be provable later.",
    ),
    (
        "noteswift", "com.bonapp.ainotes", "NoteSwift",
        "Record a meeting or a lecture, get organised notes back.",
        "Captures and transcribes meetings, lectures and passing thoughts, then turns the "
        "transcript into notes you can actually act on instead of a wall of text.",
    ),
]


def lookup(bundle_id, offline_index):
    if offline_index is not None:
        return offline_index.get(bundle_id)
    for cc in ("us", "gb", "de"):
        url = f"https://itunes.apple.com/lookup?bundleId={bundle_id}&country={cc}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.load(r)
        except Exception as exc:  # network hiccup -- try the next storefront
            print(f"  ! {bundle_id} ({cc}): {exc}")
            continue
        if data.get("resultCount"):
            time.sleep(0.25)
            return data["results"][0]
    return None


def main():
    offline_index = None
    if "--offline" in sys.argv:
        raw = json.loads((ROOT / "src" / "appstore-raw.json").read_text())
        offline_index = {r["bundleId"]: r for r in raw if r.get("trackName")}

    out, skipped = [], []
    for slug, bundle_id, name, tagline, blurb in CURATED:
        r = lookup(bundle_id, offline_index)
        if not r:
            skipped.append((slug, "not found on the App Store"))
            continue
        if r.get("sellerName") != SELLER:
            skipped.append((slug, f"seller is {r.get('sellerName')!r}, not {SELLER!r}"))
            continue
        out.append({
            "slug": slug,
            "name": name,
            "storeName": r["trackName"],
            "tagline": tagline.replace(" -- ", " — "),
            "blurb": blurb.replace(" -- ", " — "),
            "bundleId": bundle_id,
            "appId": r["trackId"],
            "storeUrl": (r.get("trackViewUrl") or "").split("?")[0],
            "category": r.get("primaryGenreName"),
            "rating": round(r["averageUserRating"], 2) if r.get("averageUserRating") else None,
            "ratingCount": r.get("userRatingCount") or 0,
            "price": r.get("formattedPrice"),
            "age": r.get("contentAdvisoryRating"),
            "updated": (r.get("currentVersionReleaseDate") or "")[:10],
            "released": (r.get("releaseDate") or "")[:10],
            "languages": len(r.get("languageCodesISO2A") or []),
            "iconUrl": r.get("artworkUrl512") or r.get("artworkUrl100"),
            "shotUrls": r.get("screenshotUrls") or [],
        })

    out.sort(key=lambda a: -a["ratingCount"])
    (ROOT / "src" / "apps.json").write_text(json.dumps(out, indent=1) + "\n")

    total = sum(a["ratingCount"] for a in out)
    weighted = sum((a["rating"] or 0) * a["ratingCount"] for a in out) / total
    print(f"{len(out)} apps -> src/apps.json")
    print(f"{total:,} ratings, weighted average {weighted:.2f}")
    for slug, why in skipped:
        print(f"skipped {slug}: {why}")


if __name__ == "__main__":
    main()
