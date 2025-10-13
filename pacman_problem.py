from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Set, Tuple

Coordinate = Tuple[int, int]


def _transform_pos(pos: Coordinate, rotation_index: int, width: int, height: int) -> Coordinate:
    """Rotate a position clockwise by 90° * rotation_index."""
    x, y = pos
    r = rotation_index % 4
    if r == 0:
        return x, y
    if r == 1:
        return y, width - 1 - x
    if r == 2:
        return width - 1 - x, height - 1 - y
    return height - 1 - y, x


def _inverse_transform_pos(pos: Coordinate, rotation_index: int, width: int, height: int) -> Coordinate:
    """Inverse rotation for _transform_pos (explicit to handle swapped dimensions)."""
    r = rotation_index % 4
    x, y = pos
    if r == 0:
        return x, y
    if r == 1:
        return (width - 1 - y, x)
    if r == 2:
        return (width - 1 - x, height - 1 - y)
    # r == 3
    return (y, height - 1 - x)


def _rotate_points(points: Iterable[Coordinate], rotation_index: int, width: int, height: int) -> FrozenSet[Coordinate]:
    return frozenset(_transform_pos(p, rotation_index, width, height) for p in points)


@dataclass(frozen=True)
class PacmanSearchState:
    pos: Coordinate
    food_left: FrozenSet[Coordinate]
    pies_left: FrozenSet[Coordinate]
    pie_timer: int
    step_mod_cycle: int  # 0..119 (4 * 30 steps)


class Ghost:
    def __init__(self, start_pos: Coordinate, move_range: int) -> None:
        self.start_pos = start_pos
        self.move_range = move_range
        self.period = (move_range - 1) * 2 if move_range > 1 else 0

    def get_position(self, g_cost: int) -> Coordinate:
        if self.period == 0:
            return self.start_pos
        phase = g_cost % self.period
        delta = phase if phase < self.move_range else self.period - phase
        return self.start_pos[0] + delta, self.start_pos[1]


class PacmanProblem:
    """Pac-Man search domain with teleports and 90° right rotations every 30 steps."""

    ROTATION_PERIOD = 30
    ROTATION_CYCLE = ROTATION_PERIOD * 4

    def __init__(self, layout_text: List[str]) -> None:
        self.layout_text = layout_text
        self.width = len(layout_text[0])
        self.height = len(layout_text)
        self._parse_layout()

    # ------------------------------------------------------------------ Layout
    def _parse_layout(self) -> None:
        walls: Set[Coordinate] = set()
        food: Set[Coordinate] = set()
        pies: Set[Coordinate] = set()
        teleports: Set[Coordinate] = set()
        self.ghosts: List[Ghost] = []
        self.exit: Optional[Coordinate] = None
        self.initial_pacman_pos: Optional[Coordinate] = None

        for y, row in enumerate(self.layout_text):
            for x, char in enumerate(row):
                pos = (x, y)
                if char == '%':
                    walls.add(pos)
                elif char == '.':
                    food.add(pos)
                elif char == 'P':
                    self.initial_pacman_pos = pos
                elif char == 'G':
                    left, right = x, x
                    while left > 0 and self.layout_text[y][left - 1] != '%':
                        left -= 1
                    while right < self.width - 1 and self.layout_text[y][right + 1] != '%':
                        right += 1
                    self.ghosts.append(Ghost((left, y), right - left + 1))
                elif char == 'O':
                    pies.add(pos)
                elif char == 'E':
                    self.exit = pos
                elif char == 'T':
                    teleports.add(pos)

        if self.initial_pacman_pos is None:
            raise ValueError("Layout missing Pacman start 'P'.")

        # Teleports fallback: inner corners just inside the outer wall frame.
        if not teleports:
            candidates = [
                (1, 1),
                (self.width - 2, 1),
                (1, self.height - 2),
                (self.width - 2, self.height - 2),
            ]
            for corner in candidates:
                if 0 <= corner[0] < self.width and 0 <= corner[1] < self.height and corner not in walls:
                    teleports.add(corner)

        self.base_walls = frozenset(walls)
        self.initial_food = frozenset(food)
        self.initial_pies = frozenset(pies)
        self.teleports_base = frozenset(teleports)

        # Legacy attributes for external modules.
        self.walls = [self.base_walls]
        self.teleports = self.teleports_base
        self.pies = self.initial_pies
        self.pie_duration = 5

        # Precompute rotated geometries so we can "paste" a rotated map quickly.
        self.rotated_dimensions: List[Tuple[int, int]] = [
            (self.width, self.height),
            (self.height, self.width),
            (self.width, self.height),
            (self.height, self.width),
        ]
        self.rotated_walls = [
            _rotate_points(self.base_walls, r, self.width, self.height) for r in range(4)
        ]
        self.rotated_teleports = [
            _rotate_points(self.teleports_base, r, self.width, self.height) for r in range(4)
        ]
        self.rotated_exit = [
            _transform_pos(self.exit, r, self.width, self.height) if self.exit else None for r in range(4)
        ]

    # ------------------------------------------------------------------ Helpers
    def _current_rotation(self, step_mod_cycle: int) -> int:
        return (step_mod_cycle // self.ROTATION_PERIOD) % 4

    def _rotate_state_components(
        self,
        pos: Coordinate,
        food: FrozenSet[Coordinate],
        pies: FrozenSet[Coordinate],
        from_rotation: int,
        to_rotation: int,
    ) -> Tuple[Coordinate, FrozenSet[Coordinate], FrozenSet[Coordinate]]:
        if from_rotation == to_rotation:
            return pos, food, pies

        base_pos = _inverse_transform_pos(pos, from_rotation, self.width, self.height)
        new_pos = _transform_pos(base_pos, to_rotation, self.width, self.height)

        base_food = (
            _inverse_transform_pos(f, from_rotation, self.width, self.height) for f in food
        )
        new_food = frozenset(
            _transform_pos(f, to_rotation, self.width, self.height) for f in base_food
        )

        base_pies = (
            _inverse_transform_pos(p, from_rotation, self.width, self.height) for p in pies
        )
        new_pies = frozenset(
            _transform_pos(p, to_rotation, self.width, self.height) for p in base_pies
        )

        return new_pos, new_food, new_pies

    def _ghost_positions(self, g_cost: int, rotation: int) -> Set[Coordinate]:
        if not self.ghosts:
            return set()
        return {
            _transform_pos(ghost.get_position(g_cost), rotation, self.width, self.height)
            for ghost in self.ghosts
        }

    # ------------------------------------------------------------------ API
    def get_initial_state(self) -> PacmanSearchState:
        return PacmanSearchState(
            pos=self.initial_pacman_pos,  # type: ignore[arg-type]
            food_left=self.initial_food,
            pies_left=self.initial_pies,
            pie_timer=0,
            step_mod_cycle=0,
        )

    def is_goal(self, state: PacmanSearchState) -> bool:
        if state.food_left:
            return False
        if not self.exit:
            return True
        rotation = self._current_rotation(state.step_mod_cycle)
        exit_pos = self.rotated_exit[rotation]
        return state.pos == exit_pos

    def get_successors(
        self,
        current_state: PacmanSearchState,
        current_g_cost: int,
    ) -> List[Tuple[str, PacmanSearchState]]:
        successors: List[Tuple[str, PacmanSearchState]] = []
        next_g_cost = current_g_cost + 1

        current_rotation = self._current_rotation(current_state.step_mod_cycle)
        width_rot, height_rot = self.rotated_dimensions[current_rotation]
        current_walls = self.rotated_walls[current_rotation]
        current_teleports = self.rotated_teleports[current_rotation]
        ghost_positions = self._ghost_positions(next_g_cost, current_rotation)

        actions = {
            "North": (0, -1),
            "South": (0, 1),
            "West": (-1, 0),
            "East": (1, 0),
            "Stop": (0, 0),
        }

        def rotate_after_steps(
            pos: Coordinate,
            food: FrozenSet[Coordinate],
            pies: FrozenSet[Coordinate],
            next_step_mod: int,
        ) -> Tuple[int, Coordinate, FrozenSet[Coordinate], FrozenSet[Coordinate]]:
            next_rotation = self._current_rotation(next_step_mod)
            if next_rotation != current_rotation:
                pos, food, pies = self._rotate_state_components(
                    pos, food, pies, current_rotation, next_rotation
                )
            return next_rotation, pos, food, pies

        next_step_mod = (current_state.step_mod_cycle + 1) % self.ROTATION_CYCLE

        for name, (dx, dy) in actions.items():
            nx, ny = current_state.pos[0] + dx, current_state.pos[1] + dy
            if not (0 <= nx < width_rot and 0 <= ny < height_rot):
                continue
            next_pos = (nx, ny)
            if (next_pos in current_walls and current_state.pie_timer <= 0) or next_pos in ghost_positions:
                continue

            pie_timer = max(0, current_state.pie_timer - 1)
            next_pies = current_state.pies_left
            if next_pos in current_state.pies_left:
                pie_timer = self.pie_duration
                next_pies = current_state.pies_left - {next_pos}

            next_food = current_state.food_left - {next_pos}
            next_rotation, rotated_pos, rotated_food, rotated_pies = rotate_after_steps(
                next_pos, next_food, next_pies, next_step_mod
            )

            successors.append(
                (
                    name,
                    PacmanSearchState(
                        pos=rotated_pos,
                        food_left=rotated_food,
                        pies_left=rotated_pies,
                        pie_timer=pie_timer,
                        step_mod_cycle=next_step_mod,
                    ),
                )
            )

        if current_state.pos in current_teleports:
            for target in current_teleports:
                if target == current_state.pos or target in ghost_positions:
                    continue
                pie_timer = max(0, current_state.pie_timer - 1)
                next_pies = current_state.pies_left
                if target in current_state.pies_left:
                    pie_timer = self.pie_duration
                    next_pies = current_state.pies_left - {target}

                next_food = current_state.food_left - {target}
                next_rotation, rotated_pos, rotated_food, rotated_pies = rotate_after_steps(
                    target, next_food, next_pies, next_step_mod
                )

                successors.append(
                    (
                        f"Teleport to {target}",
                        PacmanSearchState(
                            pos=rotated_pos,
                            food_left=rotated_food,
                            pies_left=rotated_pies,
                            pie_timer=pie_timer,
                            step_mod_cycle=next_step_mod,
                        ),
                    )
                )

        return successors
