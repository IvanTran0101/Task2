Pac‑Man Assets (drop‑in sprites)

Place your PNG images in this `assets/` folder. The game will auto‑load them if present; if a file is missing, it falls back to the built‑in vector drawings.

General rules
- Format: PNG with transparency (recommended)
- Size: any; images are scaled to the game `tile_size`
- Origin/alignment: images are centered on each tile

Tile images (optional)
- wall.png
- food.png
- pie.png
- teleport.png
- exit.png

Teleport animation (optional)
- Provide 4+ frames named `teleport_0.png`, `teleport_1.png`, `teleport_2.png`, `teleport_3.png`.
- The game will animate these frames automatically (~8 fps). If not present, it falls back to `teleport.png` or the default vector style.

Animated GIF support
- You can instead drop a single `teleport.gif` (animated). If present, the game will prefer it over `teleport_*.png`.
- Per-frame durations embedded in the GIF are respected for playback.

Pac‑Man sprites (optional)
Provide 1+ frames per direction. The engine will cycle frames for a simple animation.
- pacman_right_0.png, pacman_right_1.png, ...
- pacman_left_0.png,  pacman_left_1.png,  ...
- pacman_up_0.png,    pacman_up_1.png,    ...
- pacman_down_0.png,  pacman_down_1.png,  ...

Ghost sprites (optional)
Provide 1+ frames shared by all ghosts (or duplicate with color if you like).
- ghost_0.png, ghost_1.png, ghost_2.png, ...

Notes
- You can start with a single frame per direction (e.g., only `pacman_right_0.png`) and it will render without animation.
- If only some directions are provided, missing directions fall back to built‑in drawing.
- Animation speed can be adjusted via `PacmanGame.animation_delay` or by editing the frame timing in `asset_manager.py`.

Using a sprite sheet (like the one you shared)
- You can slice a sprite sheet into files this project understands.
- Requires Pillow: `pip install Pillow`
- Create a JSON manifest (example below) at `assets/spritesheet_manifest.json` and run:
  - `python3 tools/slice_sheet.py assets/spritesheet_manifest.json`

Example manifest (edit x,y,w,h for your sheet):
{
  "source": "assets/pacman_sheet.png",
  "tile_size": 20,
  "scale_to_tile": true,
  "outputs": [
    {"name": "pacman_right_0.png", "rect": [X1, Y1, W1, H1]},
    {"name": "pacman_right_1.png", "rect": [X2, Y2, W2, H2]},
    {"name": "pacman_up_0.png",    "rect": [X3, Y3, W3, H3]},
    {"name": "pacman_left_0.png",  "rect": [X4, Y4, W4, H4]},
    {"name": "pacman_down_0.png",  "rect": [X5, Y5, W5, H5]},
    {"name": "ghost_0.png",        "rect": [X6, Y6, W6, H6]},
    {"name": "ghost_1.png",        "rect": [X7, Y7, W7, H7]},
    {"name": "food.png",            "rect": [X8, Y8, W8, H8]},
    {"name": "wall.png",            "rect": [X9, Y9, W9, H9]}
  ]
}

Tip: For the classic sheet, Pac‑Man frames are usually at the top‑right (mouth open/close in four directions), ghost rows are grouped by color beneath. Measure rectangles in any image editor and paste here.
