"""Pixel comparison of the actual four WASM renderers, not an HTML mock."""
from pathlib import Path
from PIL import Image
import numpy as np

root = Path(__file__).resolve().parents[1] / "build/qa"
for engine in ["wordcraft", "gridcraft", "deckcraft", "pdfcraft"]:
    light = np.asarray(Image.open(root / f"light-{engine}.png").convert("RGB"))
    dark = np.asarray(Image.open(root / f"dark-{engine}.png").convert("RGB"))
    # Exclude the host strip, ribbon and status bar. The native page/cell area remains.
    left = 30 if engine == "gridcraft" else 230
    light, dark = light[200:-40, left:-30], dark[200:-40, left:-30]
    white = np.all(light >= 250, axis=2)
    grey = np.all(np.abs(dark.astype(int) - 51) <= 3, axis=2)
    white_to_grey = int(np.count_nonzero(white & grey))
    black = np.all(light < 110, axis=2)
    pale = np.all(dark > 200, axis=2)
    black_to_white = int(np.count_nonzero(black & pale))
    assert white_to_grey > 10000, (engine, "Paper did not become grey", white_to_grey)
    assert black_to_white > 30, (engine, "Dark document text did not become light", black_to_white)
    print(f"PASS: {engine}: {white_to_grey:,} white-to-grey pixels; {black_to_white:,} dark-to-light text pixels")
