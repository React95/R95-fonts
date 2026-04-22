#!/usr/bin/env python3
"""
fnt2ttf.py - Convert Windows FNT bitmap fonts to TTF + WOFF2 for web use.

Reads every .fnt file under sources/ and writes a new .ttf and .woff2 next to it.
The original files are left untouched.

Usage:
    python3 scripts/fnt2ttf.py

Requirements:
    pip install monobit fonttools brotli
"""

import sys
import io
from pathlib import Path

try:
    import monobit
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.woff2 import compress as woff2_compress
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install monobit fonttools brotli")

SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"

# Windows-1252 codepoints 0x80-0x9F map to these Unicode values.
# monobit already handles this, but we keep it for reference / override if needed.
CP1252_TO_UNICODE = {
    0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E,
    0x85: 0x2026, 0x86: 0x2020, 0x87: 0x2021, 0x88: 0x02C6,
    0x89: 0x2030, 0x8A: 0x0160, 0x8B: 0x2039, 0x8C: 0x0152,
    0x8E: 0x017D, 0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201C,
    0x94: 0x201D, 0x95: 0x2022, 0x96: 0x2013, 0x97: 0x2014,
    0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161, 0x9B: 0x203A,
    0x9C: 0x0153, 0x9E: 0x017E, 0x9F: 0x0178,
}


def draw_glyph(matrix: tuple, shift_up: int, pen: TTGlyphPen) -> None:
    """
    Draw a bitmap glyph as a series of rectangular TrueType contours.

    Each horizontal run of 'on' pixels in a row becomes one filled rectangle.
    Coordinates are in font units where 1 unit == 1 pixel (UPM == pixel height).

    TrueType winding: clockwise contour == filled region.
    """
    height = len(matrix)
    for row_idx, row in enumerate(matrix):
        # Y of the bottom edge of this pixel row (TTF: Y increases upward)
        y0 = shift_up + (height - 1 - row_idx)
        y1 = y0 + 1

        col = 0
        width = len(row)
        while col < width:
            if row[col]:
                x0 = col
                while col < width and row[col]:
                    col += 1
                x1 = col
                # Clockwise rectangle: top-left → top-right → bottom-right → bottom-left
                pen.moveTo((x0, y1))
                pen.lineTo((x1, y1))
                pen.lineTo((x1, y0))
                pen.lineTo((x0, y0))
                pen.closePath()
            else:
                col += 1


def build_font(fnt_path: Path) -> None:
    """Convert one .fnt file to .ttf and .woff2 written alongside it."""

    print(f"  {fnt_path.name}")

    # ── Load with monobit ──────────────────────────────────────────────────────
    fonts = monobit.load(str(fnt_path))
    mb_font = list(fonts)[0]

    # Metrics (in pixels)
    ascent  = int(mb_font.ascent)
    descent = int(mb_font.descent)
    leading = int(mb_font.leading) if mb_font.leading else 0

    # Derive pixel_height from a real glyph so we get the full cell height.
    first_char  = next(iter(mb_font.get_chars()))
    first_glyph = mb_font.get_glyph(first_char)
    pixel_height = first_glyph.height       # includes ascent + descent + internal leading
    upm = pixel_height                       # 1 font unit == 1 pixel

    # ── Collect glyphs ─────────────────────────────────────────────────────────
    glyph_order  = [".notdef"]
    advance_widths = {}
    glyph_pixels   = {}   # glyph_name → (matrix, shift_up)
    cmap           = {}   # unicode codepoint → glyph_name

    for char in mb_font.get_chars():
        char_str = char.value  # Char is a str subclass; .value gives the raw character
        if not char_str:
            continue
        cp = ord(char_str)

        glyph = mb_font.get_glyph(char)
        name  = f"uni{cp:04X}"

        if name not in glyph_order:
            glyph_order.append(name)

        advance_widths[name]  = int(glyph.advance_width)
        glyph_pixels[name]    = (glyph.pixels.as_matrix(), int(glyph.shift_up))
        cmap[cp]              = name

    # .notdef: empty box with the width of a space (or ¼ em)
    space_width = advance_widths.get("uni0020", upm // 4)
    advance_widths[".notdef"] = space_width
    glyph_pixels[".notdef"]   = ((), 0)

    # ── FontBuilder setup ──────────────────────────────────────────────────────
    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)

    # ── Draw outlines ──────────────────────────────────────────────────────────
    glyphs_table = {}
    lsb_map      = {}

    for name in glyph_order:
        pen = TTGlyphPen(None)
        matrix, shift_up = glyph_pixels[name]
        draw_glyph(matrix, shift_up, pen)
        glyph_obj = pen.glyph()

        # Recalculate bounding box; lsb comes from xMin
        if glyph_obj.numberOfContours != 0:
            glyph_obj.recalcBounds(None)
            lsb = glyph_obj.xMin
        else:
            lsb = 0

        glyphs_table[name] = glyph_obj
        lsb_map[name]      = lsb

    fb.setupGlyf(glyphs_table)

    # ── Horizontal metrics ─────────────────────────────────────────────────────
    metrics = {
        name: (advance_widths[name], lsb_map[name])
        for name in glyph_order
    }
    fb.setupHorizontalMetrics(metrics)

    # ── Head / hhea / OS/2 / name / post ─────────────────────────────────────
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)

    font_name = str(mb_font.name) if mb_font.name else fnt_path.stem
    # Derive a clean family name  (e.g. "R95 Sans Serif 14pt")
    family = font_name.replace("MS Serif", "R95 Sans Serif")

    fb.setupNameTable({
        "familyName": family,
        "styleName":  "Regular",
        "fullName":   family,
        "version":    "Version 2.0",
        "psName":     family.replace(" ", ""),
        "copyright": (
            "Original bitmap: Copyright Microsoft Corp. 1987. "
            "All rights reserved. "
            "TTF conversion by Gabriel Daltoso."
        ),
    })

    fb.setupOS2(
        sTypoAscender   = ascent,
        sTypoDescender  = -descent,
        sTypoLineGap    = leading,
        usWinAscent     = ascent,
        usWinDescent    = descent,
        sxHeight        = ascent,           # approximation
        sCapHeight      = ascent,
        fsType          = 0,                # installable embedding
    )

    fb.setupPost(isFixedPitch=False)

    fb.setupHead(unitsPerEm=upm)

    # ── Save TTF ───────────────────────────────────────────────────────────────
    ttf_path = fnt_path.with_suffix(".ttf")
    fb.font.save(str(ttf_path))
    print(f"    → {ttf_path.name}")

    # ── Save WOFF2 ─────────────────────────────────────────────────────────────
    woff2_path = fnt_path.with_suffix(".woff2")
    buf = io.BytesIO()
    woff2_compress(str(ttf_path), buf)
    woff2_path.write_bytes(buf.getvalue())
    print(f"    → {woff2_path.name}")


def main() -> None:
    fnt_files = sorted(SOURCES_DIR.rglob("*.fnt"))
    if not fnt_files:
        sys.exit(f"No .fnt files found under {SOURCES_DIR}")

    print(f"Converting {len(fnt_files)} font(s)…\n")
    for fnt_path in fnt_files:
        build_font(fnt_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
