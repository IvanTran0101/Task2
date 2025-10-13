# strategies.py
# FINAL, CORRECTED, AND OPTIMAL VERSION: Uses a simple, provably admissible heuristic.

from search import a_star_search

def chebyshev_distance(pos1, pos2):
    """A fast and admissible heuristic for grid-based pathfinding."""
    return max(abs(pos1[0] - pos2[0]), abs(pos1[1] - pos2[1]))

def pacman_heuristic(state, problem):
    """
    The final, corrected, and admissible heuristic. It is the sum of three
    non-overlapping, admissible path segments:
    1. Pacman -> Nearest Food (Chebyshev lower bound)
    2. Traversing all food -> Food Network (True-distance MST lower bound)
    3. Food Network -> Exit (True-distance to nearest food lower bound)
    """
    food_left = state.food_left
    if not food_left:
        return chebyshev_distance(state.pos, problem.exit) if problem.exit else 0
    
    # 1. Get the pre-calculated MST cost for the current set of remaining food.
    # This is a fast lookup for a value computed with true maze distances.
    mst_cost = problem.mst_cache.get(food_left, 0)
    
    # 2. Get the pre-calculated minimum true distance from the food set to the exit.
    exit_cost = problem.food_to_exit_cache.get(food_left, 0) if problem.exit else 0
    
    # 3. Calculate the admissible cost to connect Pacman to the food network.
    # The cheapest way is an admissible estimate to the nearest food pellet.
    connect_cost = min(chebyshev_distance(state.pos, food) for food in food_left)
    
    # The sum of these three admissible, non-overlapping components is admissible.
    return mst_cost + exit_cost + connect_cost

def solve_pacman_problem(problem):
    """
    Calls the generic A* search with the problem and the final, correct heuristic.
    """
    return a_star_search(problem, pacman_heuristic)