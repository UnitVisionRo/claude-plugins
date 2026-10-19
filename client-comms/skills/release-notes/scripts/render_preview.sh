#!/usr/bin/env bash
# render_preview.sh — screenshot the .html preview in a headless browser, so you can look at it.
#
# Usage:   bash render_preview.sh <release-folder>/release-notes.html [out.png]
#
# Browser: $BROWSER if set (on WSL2 this is Windows Edge), else the first of chromium, google-chrome,
# microsoft-edge found on PATH. Under WSL2 a Windows browser cannot read a Linux path, so the file URL
# goes through `wslpath -w` (\\wsl.localhost\<distro>\...).
# The window is tall on purpose: --screenshot captures the viewport only, not the full page.
set -euo pipefail

html="$(realpath "${1:?usage: render_preview.sh <file.html> [out.png]}")"
out="$(realpath -m "${2:-${html%.html}-preview.png}")"
height="${PREVIEW_HEIGHT:-6000}"

browser="${BROWSER:-}"
if [ -z "$browser" ]; then
  for b in chromium chromium-browser google-chrome microsoft-edge; do
    if command -v "$b" >/dev/null; then browser="$b"; break; fi
  done
fi
[ -n "$browser" ] || { echo "no headless browser found; set BROWSER" >&2; exit 1; }

case "$browser" in
  /mnt/*)  # Windows browser from WSL2: both the input URL and the output path must be Windows paths
    url="file:$(wslpath -w "$html" | sed 's#\\#/#g')"
    shot="$(wslpath -w "$out")"
    prof="$(wslpath -w "${TMPDIR:-/tmp}")\\rn-preview-$$"
    ;;
  *)
    url="file://$html"
    shot="$out"
    prof="${TMPDIR:-/tmp}/rn-preview-$$"
    ;;
esac

rm -f "$out"
# Old-style --headless writes the screenshot reliably; --headless=new can hand off to a running instance.
timeout 60 "$browser" --headless --disable-gpu --no-first-run --hide-scrollbars \
  --user-data-dir="$prof" --window-size=700,"$height" --virtual-time-budget=5000 \
  --screenshot="$shot" "$url" >/dev/null 2>&1 || true
case "$browser" in
  /mnt/*) rm -rf "${TMPDIR:-/tmp}/rn-preview-$$" 2>/dev/null || true ;;
  *)      rm -rf "$prof" 2>/dev/null || true ;;
esac

if [ -s "$out" ]; then
  echo "$out"
else
  echo "FAILED: no screenshot written (browser: $browser, url: $url)" >&2
  exit 1
fi
