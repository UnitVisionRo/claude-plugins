#!/usr/bin/env python3
"""Build a client release-notes email from content.json: .html preview, .txt and an Outlook-ready .eml.

Usage (from anywhere; paths are resolved against the folder holding content.json):

    uv run --with pillow python3 build_email.py <release-folder>/content.json

Pillow is only needed when an image is wider than MAX_WIDTH and must be downscaled; without it the build
fails and says so. The script is copied into each release folder, so a later edit is just a rebuild.

Inline markup in every text field: **bold**, nothing else. Raw HTML is rejected: it would leak into the
plain-text part. The .eml is verified after it is written (MIME tree, cid references, X-Unsent) and the
build fails loudly on any mismatch.
"""
import argparse
import html
import json
import re
import shutil
import struct
import sys
from email import message_from_bytes, policy
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

MAX_WIDTH = 1000  # stored image width; displayed at DISPLAY_WIDTH, so it stays sharp on high-DPI screens
DISPLAY_WIDTH = 600
FONT = "Segoe UI,Arial,Helvetica,sans-serif"

DEFAULT_THEME = {
    "primary": "#1a3fd6",  # header band, section headings, "Unde găsiți:" label
    "on_primary": "#ffffff",  # app name on the header band
    "on_primary_muted": "#dbe4ff",  # subtitle on the header band
    "text": "#1f2937",
    "muted": "#6b7280",  # captions, "Documentație" heading
    "page_bg": "#f3f4f6",
    "card_bg": "#ffffff",
    "where_bg": "#eef2ff",
    "notice_bg": "#fff7e6",
    "notice_border": "#f59e0b",
    "notice_title": "#92400e",
    "fixes": "#b91c1c",  # "Probleme rezolvate" heading
    "image_border": "#d1d5db",
}

DEFAULT_TITLES = {
    "notice": "De reținut",
    "features": "Funcționalități noi",
    "improvements": "Îmbunătățiri",
    "fixes": "Probleme rezolvate",
    "documentation": "Documentație",
}

CEDILLA = {"ş": "ș", "ţ": "ț", "Ş": "Ș", "Ţ": "Ț"}
IMAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*\.(png|jpe?g)$")
RAW_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


class BuildError(Exception):
    pass


# ---------------------------------------------------------------------------------------------- validation


def check_text(value, where, errors):
    """Validate one text field: Romanian comma-below letters, balanced **bold**, no raw HTML."""
    if not isinstance(value, str):
        errors.append(f"{where}: expected a string, got {type(value).__name__}")
        return
    for bad, good in CEDILLA.items():
        if bad in value:
            errors.append(f"{where}: cedilla '{bad}' — Romanian uses comma-below '{good}'")
    if value.count("**") % 2:
        errors.append(f"{where}: unbalanced ** in {value[:60]!r}")
    if RAW_TAG.search(value):
        errors.append(f"{where}: raw HTML tag — use **bold** instead ({RAW_TAG.search(value).group(0)})")


def walk_texts(node, where, errors):
    if isinstance(node, str):
        check_text(node, where, errors)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk_texts(item, f"{where}[{i}]", errors)
    elif isinstance(node, dict):
        for key, item in node.items():
            if key not in ("src", "name", "theme"):
                walk_texts(item, f"{where}.{key}", errors)


def validate(content):
    errors = []
    for key in ("app_name", "subject", "subtitle", "greeting", "intro", "documentation", "signoff"):
        if not content.get(key):
            errors.append(f"missing required field: {key}")
    if not content.get("features") and not content.get("improvements") and not content.get("fixes"):
        errors.append("nothing to announce: features, improvements and fixes are all empty")
    if not content.get("theme", {}).get("primary"):
        errors.append("theme.primary is required: take it from the app's theme, never from the default")
    unknown = set(content.get("theme", {})) - set(DEFAULT_THEME)
    if unknown:
        errors.append(f"unknown theme keys: {sorted(unknown)} (known: {sorted(DEFAULT_THEME)})")
    walk_texts({k: v for k, v in content.items() if k != "theme"}, "content", errors)
    for fi, feature in enumerate(content.get("features", [])):
        if not feature.get("title"):
            errors.append(f"features[{fi}]: missing title")
        if not any("where" in block for block in feature.get("blocks", [])):
            title = feature.get("title")
            errors.append(f"features[{fi}] ({title}): no 'where' block — every feature needs an access path")
        for bi, block in enumerate(feature.get("blocks", [])):
            if len(block) != 1 or next(iter(block)) not in ("p", "h", "where", "image"):
                errors.append(f"features[{fi}].blocks[{bi}]: a block is exactly one of p / h / where / image")
            image = block.get("image")
            if image is not None:
                for field in ("src", "alt", "caption"):
                    if not image.get(field):
                        errors.append(f"features[{fi}].blocks[{bi}].image: missing {field}")
    if errors:
        raise BuildError("content.json is invalid:\n  - " + "\n  - ".join(errors))


# ---------------------------------------------------------------------------------------------- images


def image_width(path):
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">I", data[16:20])[0]
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return struct.unpack(">H", data[i + 7:i + 9])[0]
            i += 2 + length
    raise BuildError(f"{path}: not a PNG or JPEG")


def collect_images(content, base, images_dir):
    """Copy (and downscale) every referenced image into images/. Returns [(name, cid, path)] in order."""
    images_dir.mkdir(exist_ok=True)
    cid_domain = re.sub(r"[^a-z0-9-]", "", content["app_name"].lower()) or "app"
    seen = {}
    for feature in content.get("features", []):
        for block in feature.get("blocks", []):
            image = block.get("image")
            if image is None:
                continue
            src = (base / Path(image["src"]).expanduser()).resolve()
            if not src.is_file():
                raise BuildError(f"image not found: {src}")
            name = image.get("name") or src.name.lower()
            if not IMAGE_NAME.match(name):
                raise BuildError(f"image name {name!r}: use lowercase ascii, digits and dashes (set 'name')")
            if name in seen:
                if seen[name][2] != src:
                    raise BuildError(f"two different images would both be named {name!r}")
                image["_cid"], image["_name"] = seen[name][1], name
                continue
            dest = images_dir / name
            width = image_width(src)
            if width > MAX_WIDTH:
                try:
                    from PIL import Image
                except ImportError:
                    raise BuildError(f"{src} is {width}px wide and Pillow is missing — run with: uv run --with pillow")
                with Image.open(src) as im:
                    im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS).save(dest)
            elif src != dest:
                shutil.copyfile(src, dest)
            cid = f"{Path(name).stem}@{cid_domain}"
            image["_cid"], image["_name"] = cid, name
            seen[name] = (name, cid, src)
    return [(name, cid, images_dir / name) for name, cid, _ in seen.values()]


# ---------------------------------------------------------------------------------------------- html


def inline(text):
    """Escape, then turn **bold** into <b>."""
    parts = html.escape(text, quote=False).split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


def render_html(content, theme, image_src):
    t, titles = theme, {**DEFAULT_TITLES, **content.get("titles", {})}
    base = f"font-family:{FONT};"
    p_style = f"margin:0 0 14px 0;{base}font-size:15px;line-height:1.55;color:{t['text']};"
    ul_style = f"margin:0 0 14px 0;padding-left:22px;{base}font-size:15px;line-height:1.55;color:{t['text']};"
    li_style = "margin:0 0 10px 0;"

    def para(text):
        return f'<p style="{p_style}">{inline(text)}</p>'

    def bullets(items):
        return f'<ul style="{ul_style}">' + "".join(f'<li style="{li_style}">{inline(i)}</li>' for i in items) + "</ul>"

    def h2(text, color):
        return (
            f'<h2 style="margin:32px 0 14px 0;padding-bottom:6px;border-bottom:2px solid {color};{base}'
            f'font-size:20px;color:{color};">{inline(text)}</h2>'
        )

    out = []
    out += [para(content["greeting"])] + [para(p) for p in content["intro"]]

    notice = content.get("notice", [])
    if notice:
        out.append(
            f'<div style="margin:22px 0;padding:16px 18px;background:{t["notice_bg"]};'
            f'border-left:4px solid {t["notice_border"]};border-radius:4px;">'
            f'<div style="{base}font-size:16px;font-weight:bold;color:{t["notice_title"]};margin-bottom:8px;">'
            f'{inline(titles["notice"])}</div>{bullets(notice)}</div>'
        )

    if content.get("features"):
        out.append(h2(titles["features"], t["primary"]))
        for feature in content["features"]:
            out.append(f'<h3 style="margin:22px 0 10px 0;{base}font-size:17px;color:{t["text"]};">'
                       f'{inline(feature["title"])}</h3>')
            for block in feature["blocks"]:
                if "p" in block:
                    out.append(para(block["p"]))
                elif "h" in block:
                    out.append(f'<h4 style="margin:18px 0 8px 0;{base}font-size:15px;color:{t["primary"]};">'
                               f'{inline(block["h"])}</h4>')
                elif "where" in block:
                    out.append(
                        f'<div style="margin:0 0 16px 0;padding:10px 14px;background:{t["where_bg"]};border-radius:4px;'
                        f'{base}font-size:14px;line-height:1.55;color:{t["text"]};">'
                        f'<b style="color:{t["primary"]};">Unde găsiți:</b> {inline(block["where"])}</div>'
                    )
                else:
                    image = block["image"]
                    out.append(
                        f'<div style="margin:6px 0 22px 0;text-align:center;">'
                        f'<img src="{html.escape(image_src(image))}" width="{DISPLAY_WIDTH}" '
                        f'alt="{html.escape(image["alt"])}" '
                        f'style="display:block;width:100%;max-width:{DISPLAY_WIDTH}px;'
                        f'height:auto;margin:0 auto;border:1px solid {t["image_border"]};border-radius:6px;">'
                        f'<div style="{base}font-size:13px;color:{t["muted"]};margin-top:6px;line-height:1.4;">'
                        f'{inline(image["caption"])}</div></div>'
                    )

    if content.get("improvements"):
        out += [h2(titles["improvements"], t["primary"]), bullets(content["improvements"])]
    if content.get("fixes"):
        out += [h2(titles["fixes"], t["fixes"]), bullets(content["fixes"])]
    out.append(h2(titles["documentation"], t["muted"]))
    out += [para(p) for p in content["documentation"]]
    out += [para(p) for p in content.get("closing", [])]
    signoff = "<br>".join(inline(line) for line in content["signoff"].split("\n"))
    out.append(f'<p style="{p_style}margin-top:20px;">{signoff}</p>')

    body = "\n".join(out)
    return f"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(content["subject"])}</title></head>
<body style="margin:0;padding:0;background:{t['page_bg']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{t['page_bg']};"><tr>
<td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;\
background:{t['card_bg']};border-radius:8px;">
<tr><td style="background:{t['primary']};padding:22px 24px;border-radius:8px 8px 0 0;">
<div style="{base}font-size:24px;font-weight:bold;color:{t['on_primary']};">{inline(content['app_name'])}</div>
<div style="{base}font-size:15px;color:{t['on_primary_muted']};margin-top:4px;">{inline(content['subtitle'])}</div>
</td></tr>
<tr><td style="padding:24px 24px 28px 24px;">
{body}
</td></tr></table>
</td></tr></table>
</body></html>
"""


# ---------------------------------------------------------------------------------------------- text


def plain(text):
    return text.replace("**", "")


def render_text(content):
    titles = {**DEFAULT_TITLES, **content.get("titles", {})}
    lines = [plain(content["greeting"]), ""]
    for p in content["intro"]:
        lines += [plain(p), ""]

    def section(title, items):
        lines.extend([plain(title).upper(), ""])
        for item in items:
            lines.extend([f"- {plain(item)}", ""])

    if content.get("notice"):
        section(titles["notice"], content["notice"])
    if content.get("features"):
        lines += [plain(titles["features"]).upper(), ""]
        for feature in content["features"]:
            lines += [f"* {plain(feature['title'])}", ""]
            for block in feature["blocks"]:
                if "p" in block:
                    lines += [plain(block["p"]), ""]
                elif "h" in block:
                    lines += [plain(block["h"]), ""]
                elif "where" in block:
                    lines += [f"Unde găsiți: {plain(block['where'])}", ""]
                else:
                    lines += [f"[Imagine: {plain(block['image']['caption'])}]", ""]
    if content.get("improvements"):
        section(titles["improvements"], content["improvements"])
    if content.get("fixes"):
        section(titles["fixes"], content["fixes"])
    lines += [plain(titles["documentation"]).upper(), ""]
    for p in content["documentation"] + content.get("closing", []):
        lines += [plain(p), ""]
    lines.append(plain(content["signoff"]))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------- eml


def build_eml(content, html_body, text_body, images):
    """multipart/related (type=multipart/alternative) > [alternative(text, html), image, image, ...].

    Built with email.mime on purpose: EmailMessage.add_related nests related *under* alternative, and Outlook
    classic then lists the images as attachments and shows "image not found" placeholders in the body.
    """
    root = MIMEMultipart("related", type="multipart/alternative")
    root["Subject"] = content["subject"]
    root["X-Unsent"] = "1"  # Outlook opens the file as an editable, ready-to-send draft
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    root.attach(alternative)
    for name, cid, path in images:
        subtype = "png" if name.endswith(".png") else "jpeg"
        part = MIMEImage(path.read_bytes(), _subtype=subtype, name=name)
        part["Content-ID"] = f"<{cid}>"
        part["Content-Location"] = name
        part["Content-Disposition"] = f'inline; filename="{name}"'
        root.attach(part)
    return root.as_bytes()


def verify_eml(raw, images):
    """Parse the written bytes back and assert the structure Outlook classic needs."""
    msg = message_from_bytes(raw, policy=policy.default)
    problems = []
    if msg.get_content_type() != "multipart/related":
        problems.append(f"root is {msg.get_content_type()}, expected multipart/related")
    if msg.get_param("type") != "multipart/alternative":
        problems.append('root lacks type="multipart/alternative"')
    if msg.get("X-Unsent") != "1":
        problems.append("missing X-Unsent: 1")
    parts = list(msg.iter_parts())
    if not parts or parts[0].get_content_type() != "multipart/alternative":
        problems.append("first child of related is not multipart/alternative")
        raise BuildError("eml verification failed:\n  - " + "\n  - ".join(problems))
    alt = [p.get_content_type() for p in parts[0].iter_parts()]
    if alt != ["text/plain", "text/html"]:
        problems.append(f"alternative holds {alt}, expected ['text/plain', 'text/html']")
    text = next(parts[0].iter_parts()).get_content()
    if RAW_TAG.search(text) or "**" in text:
        problems.append("plain-text part contains markup")
    html_text = list(parts[0].iter_parts())[1].get_content()
    referenced = set(re.findall(r'src="cid:([^"]+)"', html_text))
    attached = {}
    for part in parts[1:]:
        cid = (part.get("Content-ID") or "").strip("<>")
        attached[cid] = part
        if not part.get_content_type().startswith("image/"):
            problems.append(f"non-image part {part.get_content_type()} after the alternative")
        if not (part.get("Content-Disposition") or "").startswith("inline"):
            problems.append(f"{cid}: Content-Disposition is not inline")
        if not part.get("Content-Location"):
            problems.append(f"{cid}: missing Content-Location")
    if referenced - set(attached):
        problems.append(f"cid referenced but not attached: {sorted(referenced - set(attached))}")
    if set(attached) - referenced:
        problems.append(f"image attached but never referenced: {sorted(set(attached) - referenced)}")
    if len(attached) != len(images):
        problems.append(f"{len(attached)} image parts, expected {len(images)}")
    if problems:
        raise BuildError("eml verification failed:\n  - " + "\n  - ".join(problems))
    return sorted(referenced)


# ---------------------------------------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("content", type=Path, help="path to content.json")
    parser.add_argument("--basename", default="release-notes", help="output file stem (default: release-notes)")
    args = parser.parse_args()

    content_path = args.content.resolve()
    folder = content_path.parent
    try:
        content = json.loads(content_path.read_text(encoding="utf-8"))
        validate(content)
        theme = {**DEFAULT_THEME, **content.get("theme", {})}
        images = collect_images(content, folder, folder / "images")
        preview = render_html(content, theme, lambda image: f"images/{image['_name']}")
        email_html = render_html(content, theme, lambda image: f"cid:{image['_cid']}")
        text = render_text(content)
        raw = build_eml(content, email_html, text, images)
        cids = verify_eml(raw, images)
    except (BuildError, json.JSONDecodeError, KeyError) as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    (folder / f"{args.basename}.html").write_text(preview, encoding="utf-8")
    (folder / f"{args.basename}.txt").write_text(text, encoding="utf-8")
    (folder / f"{args.basename}.eml").write_bytes(raw)
    print(f"built {folder}/{args.basename}.{{html,txt,eml}}")
    print(f"images: {len(images)} — cids verified: {', '.join(cids) or '(none)'}")
    if not 4 <= len(images) <= 6:
        print(f"note: {len(images)} images; 4–6 is the usual range for the significant GUI changes")
    if "[" in content["signoff"]:
        print("note: the sign-off still holds a [placeholder]")


if __name__ == "__main__":
    main()
