from collections import deque
from math import inf
from typing import Dict, FrozenSet, Tuple

from search import a_star_search

Coordinate = Tuple[int, int]

# Cache distance maps per (problem id, rotation, start position) to avoid repeated BFS.
_distance_cache: Dict[Tuple[int, int, Coordinate], Dict[Coordinate, int]] = {}
# Cache MST results per (problem id, rotation, food set).
_mst_cache: Dict[Tuple[int, int, FrozenSet[Coordinate]], int] = {}


def _distance_map(rotation: int, start: Coordinate, problem) -> Dict[Coordinate, int]:
    key = (id(problem), rotation, start)
    if key in _distance_cache:
        return _distance_cache[key]

    width, height = problem.rotated_dimensions[rotation]
    walls = problem.rotated_walls[rotation]
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

    _distance_cache[key] = distances
    return distances


def _nearest_food_distance(rotation: int, state, problem) -> int:
    if not state.food_left:
        return 0
    dist_map = _distance_map(rotation, state.pos, problem)
    best = min((dist_map.get(food, inf) for food in state.food_left), default=inf)
    return 0 if best is inf else best


def _mst_cost(rotation: int, foods: FrozenSet[Coordinate], problem) -> int:
    if len(foods) <= 1:
        return 0

    key = (id(problem), rotation, foods)
    if key in _mst_cache:
        return _mst_cache[key]

    foods_list = list(foods)
    visited = {foods_list[0]}
    total = 0

    while len(visited) < len(foods_list):
        best_cost = inf
        best_food = None
        for v in visited:
            dist_map = _distance_map(rotation, v, problem)
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


def _exit_tail(rotation: int, foods: FrozenSet[Coordinate], problem) -> int:
    if not problem.exit or not foods:
        return 0
    exit_pos = problem.rotated_exit[rotation]
    if exit_pos is None:
        return 0

    best = inf
    for food in foods:
        dist_map = _distance_map(rotation, food, problem)
        best = min(best, dist_map.get(exit_pos, inf))
    return 0 if best is inf else best


def pacman_heuristic(state, problem):
    # If a pie is active, the heuristic falls back to zero to stay admissible.
    if state.pie_timer > 0:
        return 0

    rotation = (state.step_mod_cycle // problem.ROTATION_PERIOD) % 4

    if not state.food_left:
        exit_pos = problem.rotated_exit[rotation]
        if not exit_pos:
            return 0
        dist_map = _distance_map(rotation, state.pos, problem)
        return dist_map.get(exit_pos, 0)

    food_set = frozenset(state.food_left)

    pac_to_food = _nearest_food_distance(rotation, state, problem)
    mst_cost = _mst_cost(rotation, food_set, problem)
    exit_tail = _exit_tail(rotation, food_set, problem)

    return pac_to_food + mst_cost + exit_tail


def solve_pacman_problem(problem):
    return a_star_search(problem, pacman_heuristic)
