#!/usr/bin/env python3
"""
fnt2ttf.py - Convert Windows FON/FNT bitmap fonts to TTF + WOFF2 for web use.

Reads every .FON file declared in FON_SPECS, extracts all embedded bitmap
fonts, converts them to TTF + WOFF2, and writes @font-face CSS files.

Output layout:
  sources/
    serif/
      96dpi/   8pt/ 10pt/ 12pt/ 14pt/ 18pt/ 24pt/
      120dpi/  8pt/ 10pt/ 12pt/ 14pt/ 18pt/ 24pt/
    sans-serif/
      96dpi/   8pt/ 10pt/ 12pt/ 14pt/ 18pt/ 24pt/
      120dpi/  8pt/ 10pt/ 12pt/ 14pt/ 18pt/ 24pt/
  serif.css           ← serif 96 dpi, all sizes
  serif-hires.css     ← serif 120 dpi, all sizes
  sans-serif.css      ← sans-serif 96 dpi, all sizes
  sans-serif-hires.css← sans-serif 120 dpi, all sizes
  index.css           ← imports all four

Usage:
    python3 scripts/fnt2ttf.py

Requirements:
    pip install monobit fonttools brotli
"""

import base64
import io
import sys
import textwrap
from pathlib import Path

try:
    import monobit
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable
    from fontTools.ttLib.woff2 import compress as woff2_compress
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install monobit fonttools brotli")

ROOT       = Path(__file__).resolve().parent.parent
SOURCES    = ROOT / "sources"
CSS        = ROOT / "css"

# Each .FON file and the family/resolution it represents.
FON_SPECS: list[tuple[str, str, int]] = [
    ("SERIFE.FON",  "serif",      96),
    ("SERIFF.FON",  "serif",     120),
    ("SSERIFE.FON", "sans-serif", 96),
    ("SSERIFF.FON", "sans-serif",120),
]

# CSS family name template.
# e.g. serif / 96dpi / 14pt  →  "R95 Serif 14pt"
# e.g. sans-serif / 120dpi   →  "R95 Sans Serif HiRes 14pt"
def css_family(family: str, dpi: int, pt: int) -> str:
    base = "R95 Serif" if family == "serif" else "R95 Sans Serif"
    hires = " HiRes" if dpi == 120 else ""
    return f"{base}{hires} {pt}pt"

# Stem used for generated files inside each size directory.
def file_stem(family: str, dpi: int, pt: int) -> str:
    tag = "serif" if family == "serif" else "sans-serif"
    res = "hires" if dpi == 120 else "vga"
    return f"R95-{tag}-{res}-{pt}pt"


# ── Glyph rendering ────────────────────────────────────────────────────────────

# Nearest designed ASCII/Latin-1 stand-in for each undesigned extended character.
# Applied when ≥5 glyphs share the same bitmap (= placeholder group in the .FON).
PLACEHOLDER_FALLBACKS: dict[int, int] = {
    0x0152: 0x004F,  # Œ → O
    0x0153: 0x006F,  # œ → o
    0x0160: 0x0053,  # Š → S
    0x0161: 0x0073,  # š → s
    0x0178: 0x0059,  # Ÿ → Y
    0x017D: 0x005A,  # Ž → Z
    0x017E: 0x007A,  # ž → z
    0x0192: 0x0066,  # ƒ → f
    0x02C6: 0x005E,  # ˆ → ^
    0x02DC: 0x007E,  # ˜ → ~
    0x2013: 0x002D,  # – → -
    0x2014: 0x002D,  # — → -
    0x201A: 0x002C,  # ‚ → ,
    0x201C: 0x0022,  # " → "
    0x201D: 0x0022,  # " → "
    0x201E: 0x0022,  # „ → "
    0x2020: 0x002B,  # † → +
    0x2021: 0x002B,  # ‡ → +
    0x2022: 0x006F,  # • → o
    0x2026: 0x002E,  # … → .
    0x2030: 0x0025,  # ‰ → %
    0x2039: 0x003C,  # ‹ → <
    0x203A: 0x003E,  # › → >
    0x20AC: 0x0045,  # € → E
    0x2122: 0x0054,  # ™ → T
}


def make_tofu_matrix(height: int, width: int) -> list[list[int]]:
    """Filled-rectangle placeholder for glyphs with no known ASCII stand-in."""
    margin_v = max(1, height // 5)
    margin_h = max(1, width // 5)
    return [
        [1 if (margin_v <= r < height - margin_v and margin_h <= c < width - margin_h) else 0
         for c in range(width)]
        for r in range(height)
    ]


def fix_broken_placeholders(
    glyph_pixels: dict,
    advance_widths: dict,
    cmap: dict,
) -> None:
    """
    Replace placeholder glyphs that share an identical bitmap.

    In the original .FON files, extended characters that were never designed
    all point to the same bitmap. Detect these groups (≥5 glyphs with
    identical pixels) and substitute each with its nearest ASCII/Latin-1
    stand-in from PLACEHOLDER_FALLBACKS, or a tofu box if none is defined.
    """
    matrix_to_names: dict[tuple, list[str]] = {}
    for name, (matrix, _) in glyph_pixels.items():
        if name == ".notdef" or not matrix:
            continue
        key = tuple(tuple(row) for row in matrix)
        matrix_to_names.setdefault(key, []).append(name)

    name_to_cp = {v: k for k, v in cmap.items()}

    for key, names in matrix_to_names.items():
        if len(names) < 5:
            continue
        h, w = len(key), len(key[0]) if key else 0
        for name in names:
            cp = name_to_cp.get(name)
            fallback_cp = PLACEHOLDER_FALLBACKS.get(cp) if cp is not None else None
            fallback_name = f"uni{fallback_cp:04X}" if fallback_cp else None
            _, su = glyph_pixels[name]
            if fallback_name and fallback_name in glyph_pixels:
                glyph_pixels[name] = (glyph_pixels[fallback_name][0], su)
                advance_widths[name] = advance_widths[fallback_name]
            elif h > 0 and w > 0:
                glyph_pixels[name] = (make_tofu_matrix(h, w), su)


def draw_glyph(matrix: tuple, shift_up: int, pen: TTGlyphPen, scale: int = 1) -> None:
    """
    Rasterise one bitmap glyph into TrueType contours.

    Each horizontal run of 'on' pixels becomes one clockwise rectangle.
    `scale` is an integer multiplier applied to all coordinates so that
    UPM = pixel_height * scale stays within the OpenType-valid range (≥ 16).
    """
    height = len(matrix)
    for row_idx, row in enumerate(matrix):
        y0 = (shift_up + (height - 1 - row_idx)) * scale   # bottom of pixel row
        y1 = y0 + scale                                      # top   of pixel row
        col, w = 0, len(row)
        while col < w:
            if row[col]:
                x0 = col
                while col < w and row[col]:
                    col += 1
                x1 = col
                pen.moveTo((x0 * scale, y1))
                pen.lineTo((x1 * scale, y1))
                pen.lineTo((x1 * scale, y0))
                pen.lineTo((x0 * scale, y0))
                pen.closePath()
            else:
                col += 1


# ── Single-font conversion ─────────────────────────────────────────────────────

def convert_font(mb_font, out_dir: Path, family: str, dpi: int, pt: int) -> tuple[Path, Path]:
    """
    Convert one monobit font object to TTF + WOFF2 in *out_dir*.
    Returns (ttf_path, woff2_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stem    = file_stem(family, dpi, pt)
    ttf_path   = out_dir / f"{stem}.ttf"
    woff2_path = out_dir / f"{stem}.woff2"

    ascent       = int(mb_font.ascent)
    descent      = int(mb_font.descent)
    leading      = int(mb_font.leading) if mb_font.leading else 0
    first_glyph  = mb_font.get_glyph(next(iter(mb_font.get_chars())))
    pixel_height = first_glyph.height   # full cell: ascent + descent + internal leading

    # OpenType requires unitsPerEm >= 16. Scale up by the smallest integer that
    # satisfies this, so all glyph coordinates remain integers.
    scale = max(1, -(-16 // pixel_height))  # ceiling division
    upm   = pixel_height * scale

    # ── Collect glyphs ────────────────────────────────────────────────────────
    glyph_order    = [".notdef"]
    advance_widths = {}
    glyph_pixels   = {}
    cmap           = {}

    for char in mb_font.get_chars():
        char_str = char.value
        if not char_str:
            continue
        cp    = ord(char_str)
        glyph = mb_font.get_glyph(char)
        name  = f"uni{cp:04X}"
        if name not in glyph_order:
            glyph_order.append(name)
        advance_widths[name] = int(glyph.advance_width) * scale
        glyph_pixels[name]   = (glyph.pixels.as_matrix(), int(glyph.shift_up))
        cmap[cp]             = name

    space_width            = advance_widths.get("uni0020", upm // 4)
    advance_widths[".notdef"] = space_width
    glyph_pixels[".notdef"]   = ((), 0)

    fix_broken_placeholders(glyph_pixels, advance_widths, cmap)

    # ── Build outlines ────────────────────────────────────────────────────────
    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)

    glyphs_table, lsb_map = {}, {}
    for name in glyph_order:
        pen        = TTGlyphPen(None)
        matrix, su = glyph_pixels[name]
        draw_glyph(matrix, su, pen, scale)
        glyph_obj  = pen.glyph()
        if glyph_obj.numberOfContours != 0:
            glyph_obj.recalcBounds(None)
            lsb = glyph_obj.xMin
        else:
            lsb = 0
        glyphs_table[name] = glyph_obj
        lsb_map[name]      = lsb

    fb.setupGlyf(glyphs_table)
    fb.setupHorizontalMetrics({n: (advance_widths[n], lsb_map[n]) for n in glyph_order})
    fb.setupHorizontalHeader(ascent=(ascent + leading) * scale, descent=-(descent * scale))

    family_name = css_family(family, dpi, pt)
    fb.setupNameTable({
        "familyName": family_name,
        "styleName":  "Regular",
        "fullName":   family_name,
        "version":    "Version 2.0",
        "psName":     family_name.replace(" ", ""),
        "copyright": (
            "Original bitmap: Copyright Microsoft Corp. 1987. "
            "All rights reserved. "
            "TTF conversion by Gabriel Daltoso."
        ),
    })
    fb.setupOS2(
        sTypoAscender  = ascent * scale,
        sTypoDescender = -(descent * scale),
        sTypoLineGap   = leading * scale,
        # usWinAscent covers ascent + leading so browsers allocate the full cell
        # and no ink is clipped at the top of the line box.
        usWinAscent    = (ascent + leading) * scale,
        usWinDescent   = descent * scale,
        sxHeight       = ascent * scale,
        sCapHeight     = ascent * scale,
        fsType         = 0,
    )
    fb.setupPost(isFixedPitch=False)
    fb.setupHead(unitsPerEm=upm)

    # gasp table: grid-fit at all sizes, no grayscale antialiasing.
    # GASP_GRIDFIT (0x0001) | GASP_SYMMETRIC_GRIDFIT (0x0004) = 0x0005
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {65535: 0x0005}
    fb.font["gasp"] = gasp

    fb.font.save(str(ttf_path))

    buf = io.BytesIO()
    woff2_compress(str(ttf_path), buf)
    woff2_path.write_bytes(buf.getvalue())

    return ttf_path, woff2_path


# ── CSS generation ─────────────────────────────────────────────────────────────

def font_face(family: str, dpi: int, pt: int, ttf_path: Path, woff2_path: Path) -> str:
    woff2_b64 = base64.b64encode(woff2_path.read_bytes()).decode()
    ttf_b64   = base64.b64encode(ttf_path.read_bytes()).decode()
    return textwrap.dedent(f"""\
        @font-face {{
          font-family: '{css_family(family, dpi, pt)}';
          font-style: normal;
          font-display: swap;
          font-weight: normal;
          src:
            url("data:font/woff2;base64,{woff2_b64}") format("woff2"),
            url("data:font/truetype;base64,{ttf_b64}") format("truetype");
        }}
    """)


def write_css(out_path: Path, blocks: list[str]) -> None:
    out_path.write_text("\n".join(blocks) + "\n")
    print(f"  css → {out_path.relative_to(ROOT)}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # family → dpi → list of (pt, ttf_path, woff2_path)
    catalog: dict[str, dict[int, list]] = {
        "serif":      {96: [], 120: []},
        "sans-serif": {96: [], 120: []},
    }

    for fon_name, family, dpi in FON_SPECS:
        fon_path = SOURCES / fon_name
        if not fon_path.exists():
            print(f"  skip (not found): {fon_name}")
            continue

        print(f"\n{fon_name}  [{family} / {dpi} dpi]")
        fonts = list(monobit.load(str(fon_path)))

        for mb_font in fonts:
            pt = int(mb_font.point_size)
            out_dir = SOURCES / family / f"{dpi}dpi" / f"{pt}pt"
            ttf, woff2 = convert_font(mb_font, out_dir, family, dpi, pt)
            size_str = f"  {pt}pt → {ttf.name} / {woff2.name}"
            print(size_str)
            catalog[family][dpi].append((pt, ttf, woff2))

    # ── Write CSS ──────────────────────────────────────────────────────────────
    print("\nWriting CSS…")

    # family_key (e.g. "sans-serif-96") → { "all": Path, "8": Path, "10": Path, … }
    css_map: dict[str, dict] = {}

    for family in ("serif", "sans-serif"):
        for dpi in (96, 120):
            entries = catalog[family][dpi]
            if not entries:
                continue
            entries.sort(key=lambda x: x[0])

            suffix   = "-hires" if dpi == 120 else ""
            key      = f"{family}{suffix}"
            css_map[key] = {}

            # ── per-size CSS files: css/{key}/{pt}pt.css ──────────────────
            variant_dir = CSS / key
            variant_dir.mkdir(parents=True, exist_ok=True)

            for pt, ttf_path, woff2_path in entries:
                block = font_face(family, dpi, pt, ttf_path, woff2_path)

                size_css  = variant_dir / f"{pt}pt.css"
                write_css(size_css, [block])
                css_map[key][str(pt)] = size_css

            # ── all-sizes CSS file: css/{key}.css ─────────────────────────
            all_imports = [
                f'@import "./{key}/{pt}pt.css";'
                for pt, _, _ in entries
            ]
            all_css = CSS / f"{key}.css"
            all_css.write_text("\n".join(all_imports) + "\n")
            print(f"  css → css/{all_css.name}")
            css_map[key]["all"] = all_css

    # ── css/index.css imports every family ───────────────────────────────────
    CSS.mkdir(parents=True, exist_ok=True)
    index_imports = [f'@import "./{v["all"].name}";' for v in css_map.values()]
    index_path = CSS / "index.css"
    index_path.write_text("\n".join(index_imports) + "\n")
    print(f"  css → css/index.css")

    # ── Print exports map ─────────────────────────────────────────────────────
    print("\nSuggested package.json exports:")
    print('  ".": "./css/index.css",')
    for key, files in css_map.items():
        print(f'  "./{key}": "./css/{files["all"].name}",')
        for pt, css_path in sorted(
            ((k, v) for k, v in files.items() if k != "all"),
            key=lambda x: int(x[0])
        ):
            print(f'  "./{key}/{pt}pt": "./css/{key}/{pt}pt.css",')

    print("\nDone.")


if __name__ == "__main__":
    main()
