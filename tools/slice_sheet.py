#!/usr/bin/env python3
"""
Sprite sheet slicer for Pac-Man assets.

Usage:
  python3 tools/slice_sheet.py assets/spritesheet_manifest.json

Manifest JSON format:
{
  "source": "assets/pacman_sheet.png",
  "tile_size": 20,                 # optional; fallback to 20 if omitted
  "scale_to_tile": true,           # optional; default true
  "outputs": [
    {"name": "pacman_right_0.png", "rect": [x, y, w, h]},
    {"name": "pacman_left_0.png",  "rect": [x, y, w, h], "transform": "flip_h"},
    {"name": "pacman_up_0.png",    "rect": [x, y, w, h], "transform": "rot270"},
    {"name": "pacman_down_0.png",  "rect": [x, y, w, h], "transform": "rot90"},
    {"name": "ghost_0.png",        "rect": [x, y, w, h]}
  ]
}

The cropped images are written to the same folder as the manifest (typically
the `assets/` folder). If `scale_to_tile` is true, each crop is scaled to
`tile_size` x `tile_size` before saving, matching the in-game scaling.
"""

import json
import os
import sys
from typing import Any, Dict, List

try:
    from PIL import Image
except ImportError as e:
    print("This tool requires Pillow. Install with: pip install Pillow", file=sys.stderr)
    raise


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def main(manifest_path: str) -> int:
    manifest = load_manifest(manifest_path)
    source_path = manifest.get("source")
    if not source_path or not os.path.exists(source_path):
        print(f"Source image not found: {source_path}", file=sys.stderr)
        return 2

    tile_size = int(manifest.get("tile_size", 20))
    scale_to_tile = bool(manifest.get("scale_to_tile", True))
    outputs: List[Dict[str, Any]] = manifest.get("outputs", [])
    if not outputs:
        print("No outputs specified in manifest.", file=sys.stderr)
        return 3

    img = Image.open(source_path).convert("RGBA")

    out_dir = os.path.dirname(os.path.abspath(manifest_path))
    saved = 0
    for spec in outputs:
        name = spec.get("name")
        rect = spec.get("rect")
        transform = spec.get("transform")
        if not name or not rect or len(rect) != 4:
            print(f"Invalid entry (needs name and rect[x,y,w,h]): {spec}", file=sys.stderr)
            continue
        x, y, w, h = map(int, rect)
        crop = img.crop((x, y, x + w, y + h))
        # Optional transform (flip/rotate) applied before scaling
        if transform:
            if transform == "flip_h":
                crop = crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            elif transform == "flip_v":
                crop = crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            elif transform == "rot90":
                crop = crop.transpose(Image.Transpose.ROTATE_90)
            elif transform == "rot180":
                crop = crop.transpose(Image.Transpose.ROTATE_180)
            elif transform == "rot270":
                crop = crop.transpose(Image.Transpose.ROTATE_270)
        if scale_to_tile:
            crop = crop.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        dest_path = os.path.join(out_dir, name)
        crop.save(dest_path)
        saved += 1
        print(f"Saved {dest_path}")

    print(f"Done. {saved} images written to {out_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
