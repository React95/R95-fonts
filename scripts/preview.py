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

    if not chars_data:
        print(f"  skip {variant}/{pt}pt — no printable glyphs")
        return

    # Sort by codepoint and split into rows of ROW_W.
    chars_data.sort(key=lambda x: x[0])
    rows = [chars_data[i : i + ROW_W] for i in range(0, len(chars_data), ROW_W)]

    cell_h   = len(chars_data[0][1])          # bitmap height (same for all glyphs in a font)
    shift_up = chars_data[0][3]               # baseline offset (same for all)
    baseline = cell_h - 1 - shift_up          # row index of baseline pixel in the cell

    # Compute width of each row (sum of advance widths).
    row_widths = [sum(adv for _, _, adv, _ in row) for row in rows]
    img_w = max(row_widths) + PAD * 2
    img_h = cell_h * len(rows) + PAD * 2

    img = Image.new("L", (img_w, img_h), color=BG)
    pixels = img.load()

    for row_idx, row in enumerate(rows):
        x_off = PAD
        y_off = PAD + row_idx * cell_h
        for _, matrix, adv, _ in row:
            h = len(matrix)
            for r, row_bits in enumerate(matrix):
                py = y_off + r
                if py >= img_h:
                    continue
                for c, bit in enumerate(row_bits):
                    px = x_off + c
                    if px < img_w and bit:
                        pixels[px, py] = FG
            x_off += adv

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
