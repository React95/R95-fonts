#!/usr/bin/env python3
"""
preview.py - Generate PNG glyph-sheet previews for each R95 font variant.

Reads directly from the original .FON files via monobit (same source used by
fnt2ttf.py), renders all available printable characters at native bitmap
resolution, and saves one PNG per size per variant.

Output:
    sources/previews/sans-serif/8pt.png  … 24pt.png
    sources/previews/sans-serif-hires/8pt.png  … 24pt.png
    sources/previews/serif/8pt.png  … 24pt.png
    sources/previews/serif-hires/8pt.png  … 24pt.png

Requirements:
    pip install monobit pillow
"""

from pathlib import Path

try:
    import monobit
    from PIL import Image
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}\nRun: pip install monobit pillow")

ROOT     = Path(__file__).resolve().parent.parent
SOURCES  = ROOT / "sources"
PREVIEWS = SOURCES / "previews"

# Characters to display per row.
ROW_W = 32
BG    = 255   # white
FG    = 0     # black
PAD   = 4     # px padding around the whole sheet

FON_SPECS: list[tuple[str, str, int]] = [
    ("SSERIFE.FON", "sans-serif",      96),
    ("SSERIFF.FON", "sans-serif-hires",120),
    ("SERIFE.FON",  "serif",           96),
    ("SERIFF.FON",  "serif-hires",     120),
]


_PLACEHOLDER_FALLBACKS: dict[int, int] = {
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


def _make_tofu_matrix(height: int, width: int) -> list[list[int]]:
    margin_v = max(1, height // 5)
    margin_h = max(1, width // 5)
    return [
        [1 if (margin_v <= r < height - margin_v and margin_h <= c < width - margin_h) else 0
         for c in range(width)]
        for r in range(height)
    ]


def _fix_placeholders(chars_data: list) -> list:
    """Substitute shared-bitmap placeholder glyphs with their nearest ASCII stand-in."""
    from collections import defaultdict
    cp_to_idx = {cp: i for i, (cp, _, _, _) in enumerate(chars_data)}
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, (_, matrix, _, _) in enumerate(chars_data):
        key = tuple(tuple(row) for row in matrix)
        groups[key].append(i)
    for key, indices in groups.items():
        if len(indices) < 5:
            continue
        h, w = len(key), len(key[0]) if key else 0
        if h == 0 or w == 0:
            continue
        for i in indices:
            cp, _, adv, su = chars_data[i]
            fallback_cp = _PLACEHOLDER_FALLBACKS.get(cp)
            if fallback_cp and fallback_cp in cp_to_idx:
                _, fb_matrix, fb_adv, _ = chars_data[cp_to_idx[fallback_cp]]
                chars_data[i] = (cp, fb_matrix, fb_adv, su)
            else:
                chars_data[i] = (cp, _make_tofu_matrix(h, w), adv, su)
    return chars_data


def render_font(mb_font, variant: str, pt: int) -> None:
    """Render one bitmap font to a glyph-sheet PNG."""
    # Collect all chars that have a glyph and a printable codepoint.
    chars_data: list[tuple[int, list[list[int]], int, int]] = []

    for char in mb_font.get_chars():
        char_str = char.value
        if not char_str:
            continue
        cp = ord(char_str)
        # Keep printable ASCII and extended Latin (skip control chars, DEL)
        if cp < 0x20 or cp == 0x7F:
            continue
        glyph  = mb_font.get_glyph(char)
        matrix = glyph.pixels.as_matrix()
        if not matrix:
            continue
        chars_data.append((cp, matrix, int(glyph.advance_width), int(glyph.shift_up)))

    chars_data = _fix_placeholders(chars_data)

    if not chars_data:
        print(f"  skip {variant}/{pt}pt — no printable glyphs")
        return

    # Sort by codepoint and split into rows of ROW_W.
    chars_data.sort(key=lambda x: x[0])
    rows = [chars_data[i : i + ROW_W] for i in range(0, len(chars_data), ROW_W)]

    cell_h = len(chars_data[0][1])          # bitmap height (same for all glyphs in a font)
    cell_w = max(adv for _, _, adv, _ in chars_data)  # fixed cell width = widest glyph

    img_w = ROW_W * cell_w + PAD * 2
    img_h = cell_h * len(rows) + PAD * 2

    img = Image.new("L", (img_w, img_h), color=BG)
    pixels = img.load()

    for row_idx, row in enumerate(rows):
        y_off = PAD + row_idx * cell_h
        for col_idx, (_, matrix, _, _) in enumerate(row):
            x_cell = PAD + col_idx * cell_w
            glyph_w = len(matrix[0]) if matrix else 0
            x_off = x_cell + (cell_w - glyph_w) // 2   # center glyph in cell
            for r, row_bits in enumerate(matrix):
                py = y_off + r
                if py >= img_h:
                    continue
                for c, bit in enumerate(row_bits):
                    px = x_off + c
                    if 0 <= px < img_w and bit:
                        pixels[px, py] = FG

    out_dir = PREVIEWS / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{pt}pt.png"
    img.save(str(out_path))
    print(f"  {out_path.relative_to(ROOT)}")


def main() -> None:
    for fon_name, variant, dpi in FON_SPECS:
        fon_path = SOURCES / fon_name
        if not fon_path.exists():
            print(f"\nSkipping {variant} — {fon_name} not found")
            continue

        print(f"\n{variant}  ({fon_name})")
        fonts = list(monobit.load(str(fon_path)))
        for mb_font in fonts:
            pt = int(mb_font.point_size)
            render_font(mb_font, variant, pt)

    print("\nDone.")


if __name__ == "__main__":
    main()
