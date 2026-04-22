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

import io
import sys
import textwrap
from pathlib import Path

try:
    import monobit
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.woff2 import compress as woff2_compress
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install monobit fonttools brotli")

ROOT       = Path(__file__).resolve().parent.parent
SOURCES    = ROOT / "sources"

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

def draw_glyph(matrix: tuple, shift_up: int, pen: TTGlyphPen) -> None:
    """
    Rasterise one bitmap glyph into TrueType contours.

    Each horizontal run of 'on' pixels becomes one clockwise rectangle.
    1 font unit == 1 pixel (UPM == glyph cell height).
    """
    height = len(matrix)
    for row_idx, row in enumerate(matrix):
        y0 = shift_up + (height - 1 - row_idx)   # bottom of pixel row
        y1 = y0 + 1                                # top   of pixel row
        col, w = 0, len(row)
        while col < w:
            if row[col]:
                x0 = col
                while col < w and row[col]:
                    col += 1
                x1 = col
                pen.moveTo((x0, y1))
                pen.lineTo((x1, y1))
                pen.lineTo((x1, y0))
                pen.lineTo((x0, y0))
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
    upm          = pixel_height         # 1 unit == 1 pixel

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
        advance_widths[name] = int(glyph.advance_width)
        glyph_pixels[name]   = (glyph.pixels.as_matrix(), int(glyph.shift_up))
        cmap[cp]             = name

    space_width            = advance_widths.get("uni0020", upm // 4)
    advance_widths[".notdef"] = space_width
    glyph_pixels[".notdef"]   = ((), 0)

    # ── Build outlines ────────────────────────────────────────────────────────
    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)

    glyphs_table, lsb_map = {}, {}
    for name in glyph_order:
        pen        = TTGlyphPen(None)
        matrix, su = glyph_pixels[name]
        draw_glyph(matrix, su, pen)
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
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)

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
        sTypoAscender  = ascent,
        sTypoDescender = -descent,
        sTypoLineGap   = leading,
        usWinAscent    = ascent,
        usWinDescent   = descent,
        sxHeight       = ascent,
        sCapHeight     = ascent,
        fsType         = 0,
    )
    fb.setupPost(isFixedPitch=False)
    fb.setupHead(unitsPerEm=upm)

    fb.font.save(str(ttf_path))

    buf = io.BytesIO()
    woff2_compress(str(ttf_path), buf)
    woff2_path.write_bytes(buf.getvalue())

    return ttf_path, woff2_path


# ── CSS generation ─────────────────────────────────────────────────────────────

def font_face(family: str, dpi: int, pt: int, ttf_rel: str, woff2_rel: str) -> str:
    return textwrap.dedent(f"""\
        @font-face {{
          font-family: '{css_family(family, dpi, pt)}';
          font-style: normal;
          font-display: swap;
          font-weight: normal;
          src:
            url("{woff2_rel}") format("woff2"),
            url("{ttf_rel}") format("truetype");
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

            # ── per-size CSS files ─────────────────────────────────────────
            for pt, ttf_path, woff2_path in entries:
                ttf_rel   = "./" + ttf_path.relative_to(ROOT).as_posix()
                woff2_rel = "./" + woff2_path.relative_to(ROOT).as_posix()
                block     = font_face(family, dpi, pt, ttf_rel, woff2_rel)

                size_css  = ROOT / f"{key}-{pt}pt.css"
                write_css(size_css, [block])
                css_map[key][str(pt)] = size_css

            # ── all-sizes CSS file (imports each per-size file) ────────────
            all_imports = [
                f'@import "./{css_map[key][str(pt)].name}";'
                for pt, _, _ in entries
            ]
            all_css = ROOT / f"{key}.css"
            all_css.write_text("\n".join(all_imports) + "\n")
            print(f"  css → {all_css.name}")
            css_map[key]["all"] = all_css

    # ── index.css imports every family ────────────────────────────────────────
    index_imports = [f'@import "./{v["all"].name}";' for v in css_map.values()]
    index_path = ROOT / "index.css"
    index_path.write_text("\n".join(index_imports) + "\n")
    print(f"  css → index.css")

    # ── Print exports map ─────────────────────────────────────────────────────
    print("\nSuggested package.json exports:")
    print('  ".": "./index.css",')
    for key, files in css_map.items():
        print(f'  "./{key}": "./{files["all"].name}",')
        for pt, css_path in sorted(
            ((k, v) for k, v in files.items() if k != "all"),
            key=lambda x: int(x[0])
        ):
            print(f'  "./{key}/{pt}pt": "./{css_path.name}",')

    print("\nDone.")


if __name__ == "__main__":
    main()
