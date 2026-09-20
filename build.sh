#!/bin/bash
# Full rebuild: refresh App Store data, pull any new artwork, regenerate the site, check it.
#
#   ./build.sh              refresh ratings from the App Store, then build
#   ./build.sh --offline    build from the committed data, no network
#
set -euo pipefail
cd "$(dirname "$0")"

eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true

# The scripts target 3.9 so they run on stock macOS python3 as well as brew's. Whichever
# one is first on PATH must work, so fail loudly here rather than half-way through a build.
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
  echo "python3 is $(python3 -V 2>&1); this build needs 3.9 or newer" >&2
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

echo "==> building pages"
python3 src/build.py "${@:2}"

echo "==> checking output"
python3 src/check.py

echo
echo "Done. Preview with:  python3 -m http.server 4173  →  http://localhost:4173"
