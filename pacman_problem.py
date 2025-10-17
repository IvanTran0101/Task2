from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Set, Tuple, Dict

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
    # Set of base-map wall coordinates that have been destroyed by pies.
    broken_walls: FrozenSet[Coordinate]


class Ghost:
    def __init__(self, start_pos: Coordinate) -> None:
        self.start_pos = start_pos


class PacmanProblem:
    """Pac-Man search domain with teleports and 90° right rotations every 30 steps."""

    ROTATION_PERIOD = 30
    ROTATION_CYCLE = ROTATION_PERIOD * 4

    def __init__(self, layout_text: List[str]) -> None:
        self.layout_text = layout_text
        self.width = len(layout_text[0])
        self.height = len(layout_text)
        self._parse_layout()
        # Caches to speed up ghost position computation across the search
        # Keyed by (g_cost, rotation_index, broken_walls_base)
        self._ghost_pos_cache: Dict[Tuple[int, int, FrozenSet[Coordinate]], List[Coordinate]] = {}
        # Seed positions at the start of a rotation window: (g0, rotation, broken_walls_base)
        self._ghost_seed_cache: Dict[Tuple[int, int, FrozenSet[Coordinate]], List[Coordinate]] = {}

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
                    # Start exactly at the G position
                    self.ghosts.append(Ghost((x, y)))
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

    def _effective_walls(self, rotation: int, broken_walls_base: FrozenSet[Coordinate]) -> FrozenSet[Coordinate]:
        """Rotated walls minus any broken wall tiles (broken stored in base coords)."""
        if not broken_walls_base:
            return self.rotated_walls[rotation]
        broken_rot = frozenset(
            _transform_pos(b, rotation, self.width, self.height) for b in broken_walls_base
        )
        return self.rotated_walls[rotation] - broken_rot

    def _ghost_positions_continuous(
        self,
        g_cost: int,
        rotation: int,
        broken_walls_base: FrozenSet[Coordinate],
    ) -> List[Coordinate]:
        if not self.ghosts:
            return []

        cache_key = (g_cost, rotation, broken_walls_base)
        if cache_key in self._ghost_pos_cache:
            return self._ghost_pos_cache[cache_key]

        # Precompute rotated walls once per rotation, factoring broken walls
        width_rot, height_rot = self.rotated_dimensions[rotation]
        walls_rot = self._effective_walls(rotation, broken_walls_base)

        # Steps since this rotation started; also the tick index at rotation start
        s = g_cost % self.ROTATION_PERIOD
        g0 = g_cost - s

        # Seed positions at the start of this rotation window
        seeds_key = (g0, rotation, broken_walls_base)
        if seeds_key in self._ghost_seed_cache:
            seeds = self._ghost_seed_cache[seeds_key]
        else:
            if g0 == 0:
                seeds = [
                    _transform_pos(ghost.start_pos, rotation, self.width, self.height)
                    for ghost in self.ghosts
                ]
            else:
                prev_rot = (rotation - 1) % 4
                prev_positions = self._ghost_positions_continuous(g0 - 1, prev_rot, broken_walls_base)
                seeds = []
                for pos_prev_rot in prev_positions:
                    base_prev = _inverse_transform_pos(pos_prev_rot, prev_rot, self.width, self.height)
                    seed = _transform_pos(base_prev, rotation, self.width, self.height)
                    seeds.append(seed)
            self._ghost_seed_cache[seeds_key] = seeds

        positions: List[Coordinate] = []
        if s == 0:
            # At the boundary, ghosts are at the seeds (possibly stuck inside walls)
            positions = list(seeds)
        else:
            # Advance s steps in the current rotation's corridor from each seed
            for sx, sy in seeds:
                if not (0 <= sx < width_rot and 0 <= sy < height_rot) or (sx, sy) in walls_rot:
                    positions.append((sx, sy))
                    continue
                L = sx
                while L - 1 >= 0 and (L - 1, sy) not in walls_rot:
                    L -= 1
                R = sx
                while R + 1 < width_rot and (R + 1, sy) not in walls_rot:
                    R += 1
                N = R - L + 1
                if N <= 1:
                    positions.append((sx, sy))
                    continue
                period = (N - 1) * 2
                offset = sx - L
                delta = (offset + s) % period
                delta_ref = delta if delta <= (N - 1) else period - delta
                positions.append((L + delta_ref, sy))

        self._ghost_pos_cache[cache_key] = positions
        return positions

    # ------------------------------------------------------------------ API
    def get_initial_state(self) -> PacmanSearchState:
        return PacmanSearchState(
            pos=self.initial_pacman_pos,  # type: ignore[arg-type]
            food_left=self.initial_food,
            pies_left=self.initial_pies,
            pie_timer=0,
            step_mod_cycle=0,
            broken_walls=frozenset(),
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
        # Effective walls for this rotation exclude any walls that have been destroyed.
        base_broken = current_state.broken_walls
        current_walls = self._effective_walls(current_rotation, base_broken)
        current_teleports = self.rotated_teleports[current_rotation]
        ghost_positions_current = self._ghost_positions_continuous(
            current_g_cost, current_rotation, base_broken
        )
        ghost_positions_next = self._ghost_positions_continuous(
            next_g_cost, current_rotation, base_broken
        )
        ghost_positions_current_set = set(ghost_positions_current)
        ghost_positions_next_set = set(ghost_positions_next)
        ghost_swaps = set(zip(ghost_positions_current, ghost_positions_next))

        actions = {
            "North": (0, -1),
            "South": (0, 1),
            "West": (-1, 0),
            "East": (1, 0),
        }

        def rotate_after_steps(
            pos: Coordinate,
            food: FrozenSet[Coordinate],
            pies: FrozenSet[Coordinate],
            next_step_mod: int,
            broken_walls_base: FrozenSet[Coordinate],
        ) -> Tuple[int, Coordinate, FrozenSet[Coordinate], FrozenSet[Coordinate], Set[Coordinate]]:
            next_rotation = self._current_rotation(next_step_mod)
            if next_rotation != current_rotation:
                pos, food, pies = self._rotate_state_components(
                    pos, food, pies, current_rotation, next_rotation
                )
            if next_rotation == current_rotation:
                ghost_set = set(ghost_positions_next)
            else:
                ghost_set = set(
                    self._ghost_positions_continuous(next_g_cost, next_rotation, broken_walls_base)
                )
            return next_rotation, pos, food, pies, ghost_set

        next_step_mod = (current_state.step_mod_cycle + 1) % self.ROTATION_CYCLE

        for name, (dx, dy) in actions.items():
            nx, ny = current_state.pos[0] + dx, current_state.pos[1] + dy
            if not (0 <= nx < width_rot and 0 <= ny < height_rot):
                continue
            next_pos = (nx, ny)
            # Track if we break a wall this move (store in base coordinates)
            broke_wall_base: Optional[Coordinate] = None
            if next_pos in current_walls:
                if current_state.pie_timer <= 0:
                    # Can't enter intact wall without pie
                    continue
                # Eat/destroy the wall instead of phasing through
                broke_wall_base = _inverse_transform_pos(next_pos, current_rotation, self.width, self.height)
            # Cannot step onto a ghost's current or next position
            if next_pos in ghost_positions_current_set or next_pos in ghost_positions_next_set:
                continue
            # Pass-through swap: Pac-Man goes to a ghost's current tile while that ghost moves into Pac-Man's tile
            if (next_pos, current_state.pos) in ghost_swaps:
                continue

            # No auto-teleport on entry; explicit "Teleport to ..." actions
            # are enumerated below when standing on a teleport tile.

            pie_timer = max(0, current_state.pie_timer - 1)
            next_pies = current_state.pies_left
            if next_pos in current_state.pies_left:
                pie_timer = self.pie_duration
                next_pies = current_state.pies_left - {next_pos}

            next_food = current_state.food_left - {next_pos}
            next_broken = current_state.broken_walls if broke_wall_base is None else (current_state.broken_walls | {broke_wall_base})
            next_rotation, rotated_pos, rotated_food, rotated_pies, rotated_ghosts = rotate_after_steps(
                next_pos, next_food, next_pies, next_step_mod, next_broken
            )
            if rotated_pos in rotated_ghosts:
                continue

            successors.append(
                (
                    name,
                    PacmanSearchState(
                        pos=rotated_pos,
                        food_left=rotated_food,
                        pies_left=rotated_pies,
                        pie_timer=pie_timer,
                        step_mod_cycle=next_step_mod,
                        broken_walls=next_broken,
                    ),
                )
            )

        # Note: 'Stop' action is not part of the rules; not generated.

        if current_state.pos in current_teleports:
            for target in current_teleports:
                if (
                    target == current_state.pos
                    or target in ghost_positions_current_set
                    or target in ghost_positions_next_set
                ):
                    continue
                # Pass-through on teleport too
                if (target, current_state.pos) in ghost_swaps:
                    continue
                pie_timer = max(0, current_state.pie_timer - 1)
                next_pies = current_state.pies_left
                if target in current_state.pies_left:
                    pie_timer = self.pie_duration
                    next_pies = current_state.pies_left - {target}

                next_food = current_state.food_left - {target}
                next_rotation, rotated_pos, rotated_food, rotated_pies, rotated_ghosts = rotate_after_steps(
                    target, next_food, next_pies, next_step_mod, current_state.broken_walls
                )
                if rotated_pos in rotated_ghosts:
                    continue

                successors.append(
                    (
                        f"Teleport to {target}",
                        PacmanSearchState(
                            pos=rotated_pos,
                            food_left=rotated_food,
                            pies_left=rotated_pies,
                            pie_timer=pie_timer,
                            step_mod_cycle=next_step_mod,
                            broken_walls=current_state.broken_walls,
                        ),
                    )
                )

        return successors
