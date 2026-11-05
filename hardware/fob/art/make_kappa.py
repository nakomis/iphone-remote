# Kappa's silkscreen portrait: art/kappa.png (1-bit, white pixel = silk). The board is white with
# black silk, so the silk is Kappa's dark fur and the bare board shows his eyes and highlights.
#
# Source: Martin's Photos library, asset 6DE94A7F-F7DF-4AD6-82F4-2F50EE10356E (768x1024 preview),
# copied to art/kappa-photo.jpeg. Outline from macOS Vision's subject lift (as tinycrypt's Mu):
#
#   swift art/liftsubject.swift art/kappa-photo.jpeg /tmp/kappa_mask.png
#   python3 art/make_kappa.py art/kappa-photo.jpeg /tmp/kappa_mask.png art/kappa.png [mode]
#
# mode: "local" (default, K below) keeps as bare board only what is lighter than its
# surroundings; "global" thresholds the whole head at one level.
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

photo_path, mask_path, out_path = sys.argv[1:4]
MODE = sys.argv[4] if len(sys.argv) > 4 else "local"
K = int(sys.argv[5]) if len(sys.argv) > 5 else 14   # local: how much lighter than the surroundings
T = int(sys.argv[5]) if len(sys.argv) > 5 else 140  # global: lighter than this is bare board
WIDTH = 130                 # pixels at 0.15 mm: 19.5 mm wide
CROP = (90, 140, 715, 905)  # head, ears and ruff; drops the stub of chair at the bottom
BLUR = 10

photo = ImageOps.autocontrast(Image.open(photo_path).convert("L"), cutoff=1).crop(CROP)
mask = Image.open(mask_path).convert("L")
# The lift also takes the blurred tail that rises behind his head between the ears: cut it off
# along the top of the head.
ImageDraw.Draw(mask).polygon([(195, 0), (450, 0), (450, 205), (380, 215), (195, 195)], fill=0)
mask = mask.crop(CROP)
height = round(photo.height * WIDTH / photo.width)

big = photo.resize((WIDTH * 3, height * 3), Image.LANCZOS)
lum = np.asarray(big).astype(float)
inside = np.asarray(mask.resize((WIDTH * 3, height * 3), Image.LANCZOS)) > 127
if MODE == "local":
    local = np.asarray(big.filter(ImageFilter.GaussianBlur(BLUR))).astype(float)
    light = lum > local + K
else:
    light = lum > T
art = inside & ~light
img = Image.fromarray((art * 255).astype(np.uint8)).resize((WIDTH, height), Image.LANCZOS)
img = img.point(lambda v: 255 if v > 127 else 0).filter(ImageFilter.MedianFilter(3))
img.point(lambda v: 255 if v > 127 else 0).convert("1").save(out_path)
print(f"{out_path}: {WIDTH} x {height} px ({WIDTH * 0.15:.1f} x {height * 0.15:.1f} mm)")
