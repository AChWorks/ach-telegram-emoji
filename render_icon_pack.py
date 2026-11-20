#!/usr/bin/env python3
"""Generate Telegram-ready 100x100 static custom emoji variants from Phosphor.

Input SVGs are downloaded from a pinned Phosphor Core commit (MIT).
Outputs: editable source SVG files, PNG custom emojis, and a comparison sheet.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REVISION = "2b75f3ad12b420c9504ef05df8d2564a28f8500e"
SOURCE_BASE = f"https://raw.githubusercontent.com/phosphor-icons/core/{REVISION}"
SOURCE_DIR = ROOT / "assets" / "sources" / "phosphor"
OUTPUT_DIR = ROOT / "assets" / "generated"
PREVIEW_DIR = ROOT / "previews"

DEFAULT_ICONS = [
    "wallet", "credit-card", "check-circle", "warning-circle", "headset", "shield-check",
    "user", "gear", "gift", "bell", "globe", "lock",
]
PALETTE = [
    "#158D8E", "#3277DC", "#23A56B", "#DB8D22", "#885AC9", "#287CBE",
    "#5C6ECA", "#64748B", "#DD5B92", "#D66E40", "#249F9D", "#5B6CA8",
]
VARIANTS = ("mono", "color", "badge")
DIMENSION = 100


def fetch_checked(url: str) -> bytes:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ACh-Emoji-Workbench/1.0"})
        with urllib.request.urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: {url}")
            payload = response.read(130 * 1024)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Asset not found or unavailable (HTTP {exc.code}): {url}") from None
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"Network error obtaining source ({type(exc).__name__}): {url}") from None
    if not payload or len(payload) >= 130 * 1024:
        raise RuntimeError("Source is empty or unreasonably large")
    return payload


def source_path(name: str, weight: str) -> Path:
    filename = name + (f"-{weight}" if weight != "regular" else "") + ".svg"
    return SOURCE_DIR / weight / filename


def source_svg(name: str, weight: str) -> bytes:
    path = source_path(name, weight)
    if path.exists():
        return path.read_bytes()
    filename = path.name
    payload = fetch_checked(f"{SOURCE_BASE}/assets/{weight}/{filename}")
    if b"<svg" not in payload[:200]:
        raise RuntimeError(f"Not an SVG: {name}/{weight}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def tinted_svg(svg: bytes, color: str) -> bytes:
    # Phosphor SVGs use currentColor. Explicitly fix the rendered color.
    parser = ET.XMLParser()
    root = ET.fromstring(svg, parser=parser)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise RuntimeError("Root SVG element not found")
    # Prevent active content/external resources in any substituted SVG asset.
    allowed_tags = {"svg", "g", "path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in allowed_tags:
            raise RuntimeError("Unexpected SVG element in upstream asset")
        for key in list(element.attrib):
            attr = key.rsplit("}", 1)[-1].lower()
            if attr.startswith("on") or attr in {"href", "style"}:
                raise RuntimeError("Unexpected active SVG attribute in source")
        if element.attrib.get("fill") in (None, "currentColor", "#000", "#000000"):
            element.set("fill", color)
    return ET.tostring(root, encoding="utf-8")


def glyph(name: str, weight: str, color: str, size: int):
    svg = source_svg(name, weight)
    rendered = cairosvg.svg2png(bytestring=tinted_svg(svg, color),
                              output_width=size, output_height=size)
    return Image.open(io.BytesIO(rendered)).convert("RGBA")


def build_variant(name: str, variant: str, color: str):
    image = Image.new("RGBA", (DIMENSION, DIMENSION), (0, 0, 0, 0))
    if variant == "mono":
        mark = glyph(name, "regular", "#202B3D", 76)
        image.alpha_composite(mark, (12, 12))
    elif variant == "color":
        mark = glyph(name, "duotone", color, 78)
        image.alpha_composite(mark, (11, 11))
    elif variant == "badge":
        # Strong contrast and a rounded container, readable at emoji scale.
        drawer = ImageDraw.Draw(image)
        drawer.rounded_rectangle((4, 4, 95, 95), radius=26, fill=color)
        drawer.arc((12, 9, 89, 80), 205, 315, fill=(255, 255, 255, 48), width=2)
        mark = glyph(name, "bold", "#FFFFFF", 66)
        image.alpha_composite(mark, (17, 17))
    else:
        raise ValueError(variant)
    return image


def export(icons: list[str]):
    for name in icons:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            raise RuntimeError(f"Unsafe icon identifier: {name}")
    if len(set(icons)) != len(icons):
        raise RuntimeError("Duplicate icon names")
    if not icons:
        raise RuntimeError("No icon names specified")
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out_images = {}
    for index, name in enumerate(icons):
        color = PALETTE[index % len(PALETTE)]
        for variant in VARIANTS:
            pic = build_variant(name, variant, color)
            target = OUTPUT_DIR / variant / f"{name}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            pic.save(target, format="PNG", optimize=True)
            out_images[(name, variant)] = pic
    licence = SOURCE_DIR / "LICENSE.phosphor.txt"
    if not licence.exists():
        licence.write_bytes(fetch_checked(f"{SOURCE_BASE}/LICENSE"))
    info = {
        "library": "Phosphor Core", "license": "MIT", "revision": REVISION,
        "source": "https://github.com/phosphor-icons/core",
        "target_size": [100, 100], "variants": list(VARIANTS),
        "icons": icons,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "ATTRIBUTION.txt").write_text(
        f"Phosphor Icons (MIT)\nSource: https://github.com/phosphor-icons/core\nRevision: {REVISION}\n"
        "The original MIT license is available at assets/sources/phosphor/LICENSE.phosphor.txt\n",
        encoding="utf-8",
    )
    gallery = contact_sheet(out_images, icons)
    preview_file = PREVIEW_DIR / "phosphor-3-styles.png"
    gallery.save(preview_file, optimize=True)
    print(f"Generated {len(icons)*len(VARIANTS)} PNG files at {OUTPUT_DIR}")
    print(f"Preview: {preview_file}")


def contact_sheet(images, icons):
    # Six icon columns; groups of 3 rows show corresponding variants.
    columns = min(6, len(icons))
    segments = (len(icons) + columns - 1) // columns
    cell_w, cell_h = 168, 155
    top = 106
    canvas = Image.new("RGB", (max(640, columns * cell_w + 40),
                               top + segments * 3 * cell_h + 28), "#F2F5FA")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)
    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    draw.text((22, 17), "ACh Custom Emoji - Three Styles", fill="#182539", font=title_font)
    draw.text((22, 60), "Phosphor Core (MIT)  |  Telegram PNG 100x100  |  Static",
              fill="#536579", font=small_font)
    for segment in range(segments):
        for v_index, variant in enumerate(VARIANTS):
            for col in range(columns):
                index = segment * columns + col
                if index >= len(icons):
                    continue
                name = icons[index]
                x = 20 + col * cell_w
                y = top + (segment * 3 + v_index) * cell_h
                draw.rounded_rectangle((x, y, x + cell_w - 13, y + cell_h - 10),
                                       radius=17, fill="#FFFFFF")
                # Checkerboard for readability of transparent icons.
                draw.rounded_rectangle((x + 25, y + 10, x + 129, y + 114),
                                       radius=15, fill="#E8EDF5")
                canvas.paste(images[(name, variant)],
                             (x + 27, y + 12), images[(name, variant)])
                draw.text((x + 14, y + 118), name[:18], font=font, fill="#243448")
                draw.text((x + 14, y + 135), variant.upper(),
                          font=font, fill="#66788C")
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Create three styles of Telegram emoji from Phosphor SVGs")
    parser.add_argument("--icons", default=",".join(DEFAULT_ICONS),
                        help="Comma-separated Phosphor icon slugs; default includes 12 examples")
    args = parser.parse_args()
    icons = [x.strip() for x in args.icons.split(",") if x.strip()]
    export(icons)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
