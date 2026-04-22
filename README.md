# R95 Sans serif

[![Open in Codeflow](https://developer.stackblitz.com/img/open_in_codeflow_small.svg)](https://stackblitz.com/~/github.com/React95/R95-Sans-serif)

A port of the classic Microsoft bitmap fonts shipped with Windows 95, converted to
TTF and WOFF2 for modern web use.

| Size | Preview |
| ---- | ------- |
| 8pt  | ![8pt](./sources/8pt/MS%20Serif_8.png)    |
| 10pt | ![10pt](./sources/10pt/MS%20Serif_10.png) |
| 12pt | ![12pt](./sources/12pt/MS%20Serif_12.png) |
| 14pt | ![14pt](./sources/14pt/MS%20Serif_14.png) |
| 18pt | ![18pt](./sources/18pt/MS%20Serif_18.png) |
| 24pt | ![24pt](./sources/24pt/MS%20Serif_24.png) |

## Installation

```bash
npm install @react95/sans-serif
```

Import all sizes at once, or pick only the one you need:

```js
import '@react95/sans-serif';       // all sizes (8, 10, 12, 14, 18, 24pt)
import '@react95/sans-serif/14pt';  // single size
```

Then reference the family name in CSS:

```css
body {
  font-family: 'R95 Sans Serif 14pt';

  /*
   * For pixel-perfect rendering set font-size to the font's native
   * pixel height. Each size ships its own family name so you can mix
   * them freely without any size override.
   *
   * Native heights (px):
   *   8pt → 16px  |  10pt → 20px  |  12pt → 23px
   *  14pt → 27px  |  18pt → 33px  |  24pt → 43px
   */
  font-size: 27px;
}
```

## Contributing

### Repository layout

```
sources/
  SERIFF.FON          ← original Windows .FON container (MS Serif)
  8pt/
    MS Serif_8.fnt    ← bitmap font extracted from the .FON
    MS Serif_8.ttf    ← generated — do not edit by hand
    MS Serif_8.woff2  ← generated — do not edit by hand
    ...
  10pt/ 12pt/ 14pt/ 18pt/ 24pt/  (same structure)
scripts/
  fnt2ttf.py          ← conversion pipeline (FNT → TTF + WOFF2)
*.css                 ← @font-face declarations (one per size + index)
```

### Setting up locally

**Prerequisites:** Python 3.9+, Node.js, pnpm.

```bash
# 1. Clone and install JS dependencies
git clone https://github.com/React95/R95-Sans-serif
cd R95-Sans-serif
pnpm install

# 2. Install Python conversion dependencies
pip install monobit fonttools brotli

# 3. Start the demo app
pnpm dev
```

### Regenerating the fonts

If you change or add a `.fnt` source file, re-run the conversion script:

```bash
python3 scripts/fnt2ttf.py
```

This reads every `sources/**/*.fnt` file and writes a `.ttf` and `.woff2`
alongside it. The CSS files already point to those paths — nothing else needs
updating.

### Adding a new font variant

1. Place the `.fnt` file (extracted from a `.FON` container) under `sources/<size>pt/`.
2. Run `python3 scripts/fnt2ttf.py` to generate the TTF and WOFF2.
3. Add a matching `@font-face` block to `index.css` and create a new `<size>pt.css`.
4. Update this README's size table and the CSS `font-size` reference comment.

### Extracting `.fnt` files from a `.FON` container

A `.FON` file is a Windows NE (New Executable) binary that bundles one or more
`.fnt` bitmap fonts. You can extract them with
[**monobit**](https://github.com/robhagemans/monobit):

```bash
pip install monobit
monobit-convert SERIFF.FON --output-dir sources/
```

Or with [**fontforge**](https://fontforge.org) (scripting mode):

```python
import fontforge
font = fontforge.open("SERIFF.FON")
font.generate("output.fnt")
```

### Running the demo app

```bash
pnpm dev     # development server with hot reload
pnpm build   # production build
pnpm preview # preview the production build
```

## License

The original bitmap data is Copyright Microsoft Corp. 1987. All rights reserved.
The conversion tooling in this repository is released under the MIT License.
