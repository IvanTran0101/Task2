# pacman_problem.py
# FINAL CORRECTED VERSION: Restores the missing _transform_pos function to fix the ImportError.

import heapq
import itertools
import time
from collections import deque

def chebyshev_distance(pos1, pos2):
    """A fast and admissible heuristic for grid-based pathfinding."""
    return max(abs(pos1[0] - pos2[0]), abs(pos1[1] - pos2[1]))

# <<< START OF FIX: FUNCTION RESTORED >>>
def _transform_pos(pos, rotation_index, width, height):
    """The single source of truth for all rotation logic."""
    x, y = pos
    # Even in the no-rotation version, this is called by game.py with rotation_index=0 for drawing.
    if rotation_index == 0: return (x, y)
    elif rotation_index == 1: return (y, width - 1 - x)
    elif rotation_index == 2: return (width - 1 - x, height - 1 - y)
    elif rotation_index == 3: return (height - 1 - y, x)
    return pos
# <<< END OF FIX >>>

def _bfs_all_pairs(start_pos, walls, teleports, width, height):
    """
    Runs a BFS from a start position to find the shortest path to all other points,
    correctly handling teleports.
    """
    q = deque([(start_pos, 0)])
    visited = {start_pos}
    distances = {start_pos: 0}
    
    while q:
        curr, dist = q.popleft()
        
        # 1. Check for standard moves
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (curr[0] + dx, curr[1] + dy)
            if 0 <= neighbor[0] < width and 0 <= neighbor[1] < height and neighbor not in visited and neighbor not in walls:
                visited.add(neighbor)
                distances[neighbor] = dist + 1
                q.append((neighbor, dist + 1))
        
        # 2. If at a teleport, check teleport moves
        if curr in teleports:
            for target_corner in teleports:
                if target_corner != curr and target_corner not in visited:
                    visited.add(target_corner)
                    distances[target_corner] = dist + 1
                    q.append((target_corner, dist + 1))
                    
    return distances

def _calculate_mst_true_dist(points, true_dist_cache):
    """Calculates MST cost using pre-computed true path distances."""
    if not points or len(points) <= 1: return 0
    all_points = list(points)
    start_node = all_points[0]
    visited = {start_node}
    edges = [(true_dist_cache[start_node].get(p, float('inf')), p) for p in all_points[1:]]
    heapq.heapify(edges)
    mst_cost = 0
    while edges and len(visited) < len(all_points):
        cost, node = heapq.heappop(edges)
        if node in visited: continue
        visited.add(node)
        mst_cost += cost
        for next_node in all_points:
            if next_node not in visited:
                heapq.heappush(edges, (true_dist_cache[node].get(next_node, float('inf')), next_node))
    return mst_cost

class Ghost:
    def __init__(self, start_pos, move_range):
        self.start_pos = start_pos
        self.move_range = move_range
        self.period = (move_range - 1) * 2 if move_range > 1 else 0
    def get_position(self, g_cost):
        if self.period == 0: return self.start_pos
        phase = g_cost % self.period
        delta = phase if phase < self.move_range else self.period - phase
        return (self.start_pos[0] + delta, self.start_pos[1])

class PacmanSearchState:
    def __init__(self, pos, food_left, pie_timer):
        self.pos = pos
        self.food_left = food_left
        self.pie_timer = pie_timer
        self._hash = hash((self.pos, self.food_left, self.pie_timer))
    def __eq__(self, other):
        return isinstance(other, PacmanSearchState) and \
               self.pos == other.pos and \
               self.food_left == other.food_left and \
               self.pie_timer == other.pie_timer
    def __hash__(self):
        return self._hash

class PacmanProblem:
    def __init__(self, layout_text):
        self.layout_text = layout_text
        self.width = len(layout_text[0])
        self.height = len(layout_text)
        self.parse_layout()

    def parse_layout(self):
        original_walls, food_original = set(), set()
        self.pies, self.ghosts, self.exit = set(), [], None
        for y, row in enumerate(self.layout_text):
            for x, char in enumerate(row):
                if char == '%': original_walls.add((x, y))
                elif char == '.': food_original.add((x, y))
                elif char == 'P': self.initial_pacman_pos = (x, y)
                elif char == 'G':
                    x_left, x_right = x, x
                    while x_left > 0 and self.layout_text[y][x_left - 1] != '%': x_left -= 1
                    while x_right < self.width - 1 and self.layout_text[y][x_right + 1] != '%': x_right += 1
                    self.ghosts.append(Ghost((x_left, y), x_right - x_left + 1))
                elif char == 'O': self.pies.add((x, y))
                elif char == 'E': self.exit = (x, y)

        self.initial_food = frozenset(food_original)
        self.walls = [frozenset(original_walls)]
        self.teleports = {c for c in {(1, 1), (34, 1), (1, 16), (34, 16)} if c not in self.walls[0]}
        
        start_time = time.time()
        print("Pre-calculating true maze distances for heuristic (with teleports)...")
        points_of_interest = self.initial_food | ({self.exit} if self.exit else set())
        self.true_dist_cache = {p: _bfs_all_pairs(p, self.walls[0], self.teleports, self.width, self.height) for p in points_of_interest}

        print("Pre-calculating heuristic caches using true distances...")
        self.mst_cache = {}
        self.food_to_exit_cache = {}
        food_list = list(self.initial_food)

        for i in range(1, len(food_list) + 1):
            if i > 12:
                print(f"Warning: Too many food pellets ({len(food_list)}), stopping pre-calculation at subset size {i-1}.")
                break
            for subset in itertools.combinations(food_list, i):
                subset_fs = frozenset(subset)
                self.mst_cache[subset_fs] = _calculate_mst_true_dist(subset_fs, self.true_dist_cache)
                if self.exit:
                    min_dist = min(self.true_dist_cache[food].get(self.exit, float('inf')) for food in subset_fs)
                    self.food_to_exit_cache[subset_fs] = min_dist
        
        end_time = time.time()
        print(f"Heuristic pre-calculation complete in {end_time - start_time:.2f} seconds.")

    def get_initial_state(self):
        return PacmanSearchState(self.initial_pacman_pos, self.initial_food, 0)

    def is_goal(self, state):
        return not state.food_left and (not self.exit or state.pos == self.exit)

    def get_successors(self, current_state, current_g_cost):
        successors, next_g_cost = [], current_g_cost + 1
        current_walls = self.walls[0]
        ghost_positions = {g.get_position(next_g_cost) for g in self.ghosts}
        actions = {'North': (0, -1), 'South': (0, 1), 'West': (-1, 0), 'East': (1, 0), 'Stop': (0, 0)}
        for name, (dx, dy) in actions.items():
            next_pos = (current_state.pos[0] + dx, current_state.pos[1] + dy)
            if (next_pos in current_walls and current_state.pie_timer <= 0) or next_pos in ghost_positions:
                continue
            pie_timer = max(0, current_state.pie_timer - 1)
            if next_pos in self.pies: pie_timer = 5
            successors.append((name, PacmanSearchState(next_pos, current_state.food_left - {next_pos}, pie_timer)))
        if current_state.pos in self.teleports:
            for corner in self.teleports:
                if corner != current_state.pos:
                    pie_timer = max(0, current_state.pie_timer - 1)
                    successors.append((f"Teleport to {corner}", PacmanSearchState(corner, current_state.food_left, pie_timer)))
        return successors