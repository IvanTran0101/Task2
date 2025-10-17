import os
import glob
import pygame


class AssetManager:
    """Loads optional assets from an 'assets' directory.

    If a requested image is missing, callers should gracefully fall back
    to built-in drawing.
    """

    def __init__(self, assets_dir: str, tile_size: int) -> None:
        self.assets_dir = assets_dir
        self.tile_size = tile_size

        # Basic tiles
        self.tiles = {}
        for name in ("wall", "food", "pie", "teleport", "exit"):
            self.tiles[name] = self._load_image_optional(f"{name}.png")

        # Pac-Man directional frames
        self.pacman_frames = {
            d: self._load_sequence_optional(f"pacman_{d}_*.png") for d in ("right", "left", "up", "down")
        }

        # Ghost frames (shared by all ghosts)
        self.ghost_frames = self._load_sequence_optional("ghost_*.png")

    # ------------------------------------------------------------------ API
    def get_tile(self, name: str):
        return self.tiles.get(name)

    def get_pacman(self, direction: str, tick_ms: int):
        frames = self.pacman_frames.get(direction) or []
        if not frames:
            return None
        # 8 frames per second cycle
        idx = (tick_ms // 125) % len(frames)
        return frames[idx]

    def get_ghost(self, tick_ms: int):
        frames = self.ghost_frames
        if not frames:
            return None
        idx = (tick_ms // 150) % len(frames)
        return frames[idx]

    # ------------------------------------------------------------------ Internals
    def _load_image_optional(self, filename: str):
        path = os.path.join(self.assets_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(img, (self.tile_size, self.tile_size))
        except Exception:
            return None

    def _load_sequence_optional(self, pattern: str):
        paths = sorted(glob.glob(os.path.join(self.assets_dir, pattern)))
        images = []
        for path in paths:
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, (self.tile_size, self.tile_size))
                images.append(img)
            except Exception:
                continue
        return images

