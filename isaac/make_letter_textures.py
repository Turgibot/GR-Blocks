"""Draw one picture per block letter (isaac/letters/X.png). The scene puts it on all six faces of the block."""
import json
from pathlib import Path

import matplotlib
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "isaac" / "letters"
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path(matplotlib.__file__).parent / "mpl-data/fonts/ttf/DejaVuSans-Bold.ttf"
blocks = sorted(b for tower in json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"] for b in tower)

SIZE, BORDER = 256, 14
for b in blocks:
    im = Image.new("RGB", (SIZE, SIZE), (214, 170, 110))                 # wooden block
    d = ImageDraw.Draw(im)
    d.rectangle([BORDER, BORDER, SIZE - BORDER, SIZE - BORDER], fill=(240, 222, 186), outline=(150, 100, 50), width=6)
    font = ImageFont.truetype(str(FONT), 170)
    w, h = d.textbbox((0, 0), b, font=font)[2:]
    off = d.textbbox((0, 0), b, font=font)
    d.text(((SIZE - (off[2] - off[0])) / 2 - off[0], (SIZE - (off[3] - off[1])) / 2 - off[1]), b, font=font, fill=(40, 70, 150))
    im.save(OUT / f"{b}.png")
print("wrote", len(blocks), "pictures to", OUT.relative_to(ROOT), "->", " ".join(blocks))
