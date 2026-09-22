#!/bin/bash
# Full rebuild of the Bon App & T site.
#
# The site is hosted at bon-app.net, served from this repo's root by GitHub Pages.
# It was briefly mounted at euappsolutions.com/bonapp/, so that path is kept as redirect
# stubs pointing back here -- any URL shared in the meantime keeps working.
#
#   ./build.sh              refresh ratings from the App Store, then build
#   ./build.sh --offline    build from the committed data, no network
#
# Afterwards, commit in BOTH repos: euappsolutions-site (the site) and this one
# (source + bon-app.net redirects).
#
set -euo pipefail
cd "$(dirname "$0")"

SITE="https://bon-app.net"
MOUNTED_AT="bonapp"   # the old location inside the euappsolutions site
EU_SITE="${EU_SITE:-$(cd .. && pwd)/euappsolutions-site}"

eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true

# The scripts target 3.9 so they run on stock macOS python3 as well as brew's. Whichever
# one is first on PATH must work, so fail loudly here rather than half-way through a build.
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
  echo "python3 is $(python3 -V 2>&1); this build needs 3.9 or newer" >&2
  exit 1
}

[[ -d "$EU_SITE/.git" ]] || {
  echo "expected the euappsolutions.com checkout at $EU_SITE (set EU_SITE to override)" >&2
  exit 1
}

if [[ "${1:-}" == "--offline" ]]; then
  echo "==> using committed app data (offline)"
else
  echo "==> refreshing App Store metadata"
  python3 src/make_apps_json.py
  echo "==> fetching any missing artwork"
  python3 src/fetch_assets.py
  echo "==> regenerating social images"
  python3 src/make_social.py
fi

echo "==> building the site here (served at $SITE)"
python3 src/build.py

echo "==> checking it"
python3 src/check.py

echo "==> pointing the old euappsolutions.com/$MOUNTED_AT/ path back here"
python3 src/build.py --redirect-to "$SITE" --out "$EU_SITE/$MOUNTED_AT"

echo
echo "Done. Preview with:  python3 -m http.server 4174  →  http://localhost:4174"
echo "Commit here, and in $EU_SITE for the redirect stubs."
