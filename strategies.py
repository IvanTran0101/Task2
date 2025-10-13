# strategies.py — concise MST-centric heuristic with strict non-overlap
# h(n) = max( TRUE_dist(P->nearest food), MST_cost(foods) ) + TRUE_dist(foods->Exit)
# TRUE_dist uses BFS (4-dir + inner-corner teleports, cost+1). MST_cost is precomputed (Prim) over foods only.

from search import a_star_search
from collections import deque

# Defaults: keep A* optimal and concise.
STRICT_NO_OVERLAP = True       # use max(pac_to_food, mst_cost) + exit_tail

# ---- TRUE distance (admissible) ----
def _bfs_min_distance(start, targets, walls, teleports, width, height):
    if not targets:
        return 0
    q = deque([(start, 0)])
    seen = {start}
    while q:
        (x, y), d = q.popleft()
        if (x, y) in targets:
            return d
        # 4-dir moves
        for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
            nx, ny = x+dx, y+dy
            np = (nx, ny)
            if 0 <= nx < width and 0 <= ny < height and np not in walls and np not in seen:
                seen.add(np)
                q.append((np, d+1))
        # teleports between inner corners
        if (x, y) in teleports:
            for corner in teleports:
                if corner != (x, y) and corner not in seen:
                    seen.add(corner)
                    q.append((corner, d+1))
    return 0

# ---- Heuristic ----
def pacman_heuristic(state, problem):
    food_left = state.food_left

    # no food → go to exit (if any)
    if not food_left:
        return _bfs_min_distance(
            state.pos,
            {problem.exit} if problem.exit else set(),
            problem.walls[0], problem.teleports, problem.width, problem.height
        ) if problem.exit else 0

    pac_to_food = _bfs_min_distance(
        state.pos, food_left,
        problem.walls[0], problem.teleports,
        problem.width, problem.height
    )

    # MST over remaining foods (precomputed with Prim on TRUE distances)
    mst_cost = problem.mst_cache.get(food_left, 0)

    # foods -> exit tail (precomputed TRUE distance from set to exit)
    exit_tail = problem.food_to_exit_cache.get(food_left, 0) if problem.exit else 0

    # compose (strict non-overlap by default)
    return (max(pac_to_food, mst_cost) + exit_tail) if STRICT_NO_OVERLAP else (pac_to_food + mst_cost + exit_tail)

def solve_pacman_problem(problem):
    return a_star_search(problem, pacman_heuristic)