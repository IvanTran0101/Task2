# strategies.py
# FINAL, CORRECTED, AND OPTIMAL VERSION (MST-centric):
# Heuristic dùng MST (Prim đã precompute ở problem.mst_cache) + mini-BFS true distance.

from search import a_star_search
from collections import deque

def chebyshev_distance(pos1, pos2):
    """Giữ lại nếu nơi khác còn import; không dùng trong heuristic mới."""
    return max(abs(pos1[0] - pos2[0]), abs(pos1[1] - pos2[1]))

def _bfs_min_distance(start, targets, walls, teleports, width, height):
    """
    Trả về TRUE maze distance từ start tới ô gần nhất trong `targets`.
    Di chuyển 4 hướng, hỗ trợ teleport giữa các góc (cost +1).
    Dừng sớm khi gặp target đầu tiên. Không có target -> 0.
    """
    if not targets:
        return 0
    q = deque([(start, 0)])
    seen = {start}
    while q:
        (x, y), d = q.popleft()
        if (x, y) in targets:
            return d
        # 4 hướng
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            np = (nx, ny)
            if 0 <= nx < width and 0 <= ny < height and np not in walls and np not in seen:
                seen.add(np)
                q.append((np, d + 1))
        # Teleport giữa các góc trong tập teleports (nếu đang đứng ở 1 góc)
        if (x, y) in teleports:
            for corner in teleports:
                if corner != (x, y) and corner not in seen:
                    seen.add(corner)
                    q.append((corner, d + 1))
    # Không tới được (layout hợp lệ thì hiếm khi xảy ra)
    return 0

def pacman_heuristic(state, problem):
    """
    Heuristic MST-centric, admissible (thường cũng consistent).
    Thành phần (không chồng lấn):
      1) Pacman -> food gần nhất (TRUE maze distance bằng mini-BFS + teleport)
      2) MST cost cho tập food còn lại (precompute bằng Prim trên TRUE distances)
      3) Food network -> Exit (TRUE distance precompute từ tập food đến exit)
    """
    food_left = state.food_left

    # Không còn food: chỉ cần về exit (nếu có), dùng TRUE distance
    if not food_left:
        return _bfs_min_distance(
            state.pos,
            {problem.exit} if problem.exit else set(),
            problem.walls[0],
            problem.teleports,
            problem.width,
            problem.height
        ) if problem.exit else 0

    # 1) Pacman -> 1 food gần nhất (TRUE distance)
    pac_to_food = _bfs_min_distance(
        state.pos,
        food_left,
        problem.walls[0],
        problem.teleports,
        problem.width,
        problem.height
    )

    # 2) MST trên các food còn lại (đã precompute bằng Prim)
    mst_cost = problem.mst_cache.get(food_left, 0)

    # 3) Food network -> Exit (đã precompute)
    exit_tail = problem.food_to_exit_cache.get(food_left, 0) if problem.exit else 0

    return pac_to_food + mst_cost + exit_tail

def solve_pacman_problem(problem):
    """Gọi A* với heuristic MST-centric mới."""
    return a_star_search(problem, pacman_heuristic)