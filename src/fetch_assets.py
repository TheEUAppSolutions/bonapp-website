#!/usr/bin/env python3
"""Download App Store artwork for every app in data/apps.json and convert it to webp.

Icons  -> assets/img/icons/<slug>.webp          (256px, for the grid)
         assets/img/icons/<slug>@512.png        (512px, for og:image)
Shots  -> assets/img/shots/<slug>/<n>.webp      (540px wide, max 5 per app)

Re-runnable: skips anything already on disk unless --force is passed.
Requires cwebp (brew install webp) and sips (built into macOS).
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORCE = "--force" in sys.argv
MAX_SHOTS = 5

ICON_PX = 256
SHOT_PX = 540
QUALITY = 82


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())


def to_webp(src, dest, width, quality=QUALITY):
    dest.parent.mkdir(parents=True, exist_ok=True)
    run("cwebp", "-quiet", "-q", str(quality), "-resize", str(width), "0", str(src), "-o", str(dest))


def main():
    apps = json.loads((ROOT / "src" / "apps.json").read_text())
    tmp = ROOT / "src" / ".tmp"
    tmp.mkdir(exist_ok=True)

    for app in apps:
        slug = app["slug"]

        icon_webp = ROOT / "assets" / "img" / "icons" / f"{slug}.webp"
        icon_png = ROOT / "assets" / "img" / "icons" / f"{slug}@512.png"
        if FORCE or not icon_webp.exists():
            raw = tmp / f"{slug}-icon"
            download(app["iconUrl"], raw)
            to_webp(raw, icon_webp, ICON_PX, quality=90)
            icon_png.parent.mkdir(parents=True, exist_ok=True)
            run("sips", "-s", "format", "png", "-Z", "512", str(raw), "--out", str(icon_png))
            print(f"  icon   {slug}")

        for i, url in enumerate(app.get("shotUrls", [])[:MAX_SHOTS]):
            shot = ROOT / "assets" / "img" / "shots" / slug / f"{i}.webp"
            if not FORCE and shot.exists():
                continue
            raw = tmp / f"{slug}-{i}"
            download(url, raw)
            to_webp(raw, shot, SHOT_PX)
            print(f"  shot   {slug}/{i}")

    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()

    icons = len(list((ROOT / "assets" / "img" / "icons").glob("*.webp")))
    shots = len(list((ROOT / "assets" / "img" / "shots").rglob("*.webp")))
    print(f"\n{icons} icons, {shots} screenshots")


if __name__ == "__main__":
    main()
