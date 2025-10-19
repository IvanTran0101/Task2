from collections import deque
from math import inf
from typing import Dict, FrozenSet, Tuple

from search import a_star_search
from pacman_problem import _transform_pos, _inverse_transform_pos

Coordinate = Tuple[int, int]

# Cache distance maps over effective walls per (problem, rotation, start, broken_walls)
_distance_eff_cache: Dict[Tuple[int, int, Coordinate, FrozenSet[Coordinate]], Dict[Coordinate, int]] = {}
# Cache MST results per (problem id, rotation, food set, broken_walls).
_mst_cache: Dict[Tuple[int, int, FrozenSet[Coordinate], FrozenSet[Coordinate]], int] = {}
# Cache final heuristic values per (problem, phase_in_rotation, rotation, pos, foods, broken)
_heuristic_cache: Dict[
    Tuple[int, int, int, Coordinate, FrozenSet[Coordinate], FrozenSet[Coordinate]],
    int,
] = {}


def _effective_walls(problem, rotation: int, broken_walls_base: FrozenSet[Coordinate]) -> FrozenSet[Coordinate]:
    if not broken_walls_base:
        return problem.rotated_walls[rotation]
    broken_rot = frozenset(
        _transform_pos(b, rotation, problem.width, problem.height) for b in broken_walls_base
    )
    return problem.rotated_walls[rotation] - broken_rot


def _distance_map_effective(rotation: int, start: Coordinate, problem, broken_walls: FrozenSet[Coordinate]) -> Dict[Coordinate, int]:
    key = (id(problem), rotation, start, broken_walls)
    if key in _distance_eff_cache:
        return _distance_eff_cache[key]

    width, height = problem.rotated_dimensions[rotation]
    walls = _effective_walls(problem, rotation, broken_walls)
    teleports = problem.rotated_teleports[rotation]

    q = deque([start])
    distances = {start: 0}

    while q:
        x, y = current = q.popleft()
        base = distances[current]

        # 4-connected moves
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbour = (nx, ny)
            if neighbour in walls or neighbour in distances:
                continue
            distances[neighbour] = base + 1
            q.append(neighbour)

        # Teleport moves between corners
        if current in teleports:
            for target in teleports:
                if target == current or target in distances:
                    continue
                distances[target] = base + 1
                q.append(target)

    _distance_eff_cache[key] = distances
    return distances


def _nearest_food_distance(rotation: int, state, problem) -> int:
    if not state.food_left:
        return 0
    broken = getattr(state, 'broken_walls', frozenset())
    dist_map = _distance_map_effective(rotation, state.pos, problem, broken)
    best = min((dist_map.get(food, inf) for food in state.food_left), default=inf)
    return 0 if best is inf else best


def _mst_cost(rotation: int, foods: FrozenSet[Coordinate], problem, broken: FrozenSet[Coordinate]) -> int:
    if len(foods) <= 1:
        return 0

    key = (id(problem), rotation, foods, broken)
    if key in _mst_cache:
        return _mst_cache[key]

    foods_list = list(foods)
    visited = {foods_list[0]}
    total = 0

    while len(visited) < len(foods_list):
        best_cost = inf
        best_food = None
        for v in visited:
            dist_map = _distance_map_effective(rotation, v, problem, broken)
            for u in foods_list:
                if u in visited:
                    continue
                dist = dist_map.get(u, inf)
                if dist < best_cost:
                    best_cost = dist
                    best_food = u
        if best_food is None or best_cost is inf:
            # Unreachable food; contribute nothing to keep heuristic admissible.
            break
        visited.add(best_food)
        total += best_cost

    _mst_cache[key] = total
    return total


def _exit_tail(rotation: int, foods: FrozenSet[Coordinate], problem, broken: FrozenSet[Coordinate]) -> int:
    if not problem.exit or not foods:
        return 0
    exit_pos = problem.rotated_exit[rotation]
    if exit_pos is None:
        return 0

    best = inf
    for food in foods:
        dist_map = _distance_map_effective(rotation, food, problem, broken)
        best = min(best, dist_map.get(exit_pos, inf))
    return 0 if best is inf else best


def pacman_heuristic(state, problem):
    # If a pie is active, the heuristic falls back to zero to stay conservative.
    if state.pie_timer > 0:
        return 0

    cur_rotation = (state.step_mod_cycle // problem.ROTATION_PERIOD) % 4
    phase = state.step_mod_cycle % problem.ROTATION_PERIOD
    foods_cur = frozenset(state.food_left)
    broken = getattr(state, 'broken_walls', frozenset())

    cache_key = (id(problem), phase, cur_rotation, state.pos, foods_cur, broken)
    if cache_key in _heuristic_cache:
        return _heuristic_cache[cache_key]

    # Helper: rotate a coordinate from current rotation to target rotation.
    def _rot_coord(c):
        base = _inverse_transform_pos(c, cur_rotation, problem.width, problem.height)
        return _transform_pos(base, (cur_rotation + 1) % 4, problem.width, problem.height)

    # Heuristic in current rotation (k = 0)
    if not foods_cur:
        exit_pos_cur = problem.rotated_exit[cur_rotation]
        if not exit_pos_cur:
            _heuristic_cache[cache_key] = 0
            return 0
        dist_map_cur = _distance_map_effective(cur_rotation, state.pos, problem, broken)
        best_cur = dist_map_cur.get(exit_pos_cur, 0)
        # Phase-aware alternative: rotate once after boundary and pay waiting steps
        # Steps until the next rotation boundary
        k_boundary = problem.ROTATION_PERIOD if phase == 0 else (problem.ROTATION_PERIOD - phase)
        next_rotation = (cur_rotation + 1) % 4
        # Transform position to next rotation (foods empty)
        pos_next = _rot_coord(state.pos)
        exit_pos_next = problem.rotated_exit[next_rotation]
        if exit_pos_next is None:
            best_next = inf
        else:
            dist_map_next = _distance_map_effective(next_rotation, pos_next, problem, broken)
            best_next = dist_map_next.get(exit_pos_next, inf)
        value = min(best_cur, k_boundary + (0 if best_next is inf else best_next))
        _heuristic_cache[cache_key] = value
        return value

    # Current-rotation estimate
    pac_to_food_cur = _nearest_food_distance(cur_rotation, state, problem)
    mst_cur = _mst_cost(cur_rotation, foods_cur, problem, broken)
    exit_tail_cur = _exit_tail(cur_rotation, foods_cur, problem, broken)
    best_cur = pac_to_food_cur + mst_cur + exit_tail_cur

    # Phase-aware alternative: rotate at the next boundary and pay waiting steps
    k_boundary = problem.ROTATION_PERIOD if phase == 0 else (problem.ROTATION_PERIOD - phase)
    next_rotation = (cur_rotation + 1) % 4

    # Rotate position and foods to next rotation orientation
    pos_next = _rot_coord(state.pos)
    foods_next = frozenset(_rot_coord(f) for f in foods_cur)

    # Compute components in the next rotation
    # Distance from rotated pos to nearest rotated food
    dist_map_next = _distance_map_effective(next_rotation, pos_next, problem, broken)
    best_food_next = min((dist_map_next.get(f, inf) for f in foods_next), default=inf)
    pac_to_food_next = 0 if best_food_next is inf else best_food_next
    mst_next = _mst_cost(next_rotation, foods_next, problem, broken)
    exit_tail_next = _exit_tail(next_rotation, foods_next, problem, broken)
    best_next = k_boundary + pac_to_food_next + mst_next + exit_tail_next

    value = min(best_cur, best_next)
    _heuristic_cache[cache_key] = value
    return value


def solve_pacman_problem(problem):
    return a_star_search(problem, pacman_heuristic)
