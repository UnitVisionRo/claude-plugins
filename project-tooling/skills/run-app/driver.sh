#!/usr/bin/env bash
# driver.sh — drive the app by screenshotting routes with headless Windows Edge.
#
# This machine runs WSL2; the only browser is Windows Edge at $BROWSER
# (/mnt/c/.../msedge.exe). A Linux automation lib can't attach to a Windows .exe, so we
# use Edge's headless `--screenshot` mode: navigate to a URL, render it, write a PNG, exit.
# Windows Edge reaches the WSL dev server over localhost (WSL2 localhost forwarding).
#
# Usage:   BASE_URL=https://localhost:<frontend-port> driver.sh [route ...]
#          SHOTS_DIR=cv-shots BASE_URL=... driver.sh /dashboard /reports
#
# BASE_URL is required — there is no default port, because every project uses its own.
# SHOTS_DIR names the Windows output folder; it defaults to the repo directory name.
# Prints the WSL path of each PNG it writes (open it with the Read tool).
set -euo pipefail

: "${BASE_URL:?BASE_URL is not set — pass the frontend dev-server URL, e.g. https://localhost:8080}"
: "${BROWSER:?BROWSER env var is not set (expected the Windows Edge path)}"

# Default the output folder to "<repo>-shots" so parallel projects never collide.
if [ -z "${SHOTS_DIR:-}" ]; then
  repo="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"
  SHOTS_DIR="${repo}-shots"
fi

# Edge writes to a Windows path; we read the same dir from WSL via /mnt/c.
WIN_USER="${WIN_USER:-$USER}"
WIN_DIR="C:\\Users\\${WIN_USER}\\${SHOTS_DIR}"
WSL_DIR="/mnt/c/Users/${WIN_USER}/${SHOTS_DIR}"
mkdir -p "$WSL_DIR"

routes=("$@"); [ ${#routes[@]} -eq 0 ] && routes=(/)

for route in "${routes[@]}"; do
  # /reports -> reports ; / -> root ; strip query punctuation for the filename
  name="$(printf '%s' "$route" | sed 's#^/##; s#/#_#g; s/[?=&]/-/g')"
  [ -z "$name" ] && name=root
  rm -f "$WSL_DIR/$name.png"
  # Unique profile per launch: a shared --user-data-dir deadlocks on the profile lock
  # when launches run back to back. `timeout` caps a hung launch so the next still runs.
  prof="$WIN_DIR\\p_${name}_$$"
  # `--headless` (old mode) writes the screenshot reliably; `--headless=new` intermittently
  # hands the invocation to an already-running Edge and exits 0 without writing anything.
  timeout 60 "$BROWSER" --headless --disable-gpu --no-first-run --ignore-certificate-errors \
    --user-data-dir="$prof" \
    --window-size=1440,900 --virtual-time-budget=8000 \
    --screenshot="$WIN_DIR\\$name.png" \
    "$BASE_URL$route" >/dev/null 2>&1 || true
  rm -rf "$WSL_DIR/p_${name}_$$" 2>/dev/null || true
  if [ -s "$WSL_DIR/$name.png" ]; then
    echo "$WSL_DIR/$name.png"
  else
    echo "FAILED: $route (no PNG written)" >&2
  fi
done
