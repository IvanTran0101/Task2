# search.py
# CORRECTED VERSION: Passes the current g_cost to get_successors.

import heapq
import time

class Node:
    def __init__(self, state, parent, action, g_cost):
        self.state = state
        self.parent = parent
        self.action = action
        self.g_cost = g_cost

    def __lt__(self, other):
        return self.g_cost < other.g_cost

def a_star_search(problem, heuristic):
    print("Starting A* search...")
    start_time = time.time()
    
    initial_state = problem.get_initial_state()
    start_node = Node(initial_state, parent=None, action=None, g_cost=0)
    
    frontier = []
    tie_breaker = 0
    f_cost = start_node.g_cost + heuristic(start_node.state, problem)
    heapq.heappush(frontier, (f_cost, tie_breaker, start_node))
    
    explored = set()
    
    while frontier:
        _, _, current_node = heapq.heappop(frontier)

        if current_node.state in explored:
            continue
            
        if problem.is_goal(current_node.state):
            end_time = time.time()
            print(f"Solution found in {end_time - start_time:.4f} seconds.")
            print(f"Nodes explored: {len(explored)}")
            
            path = []
            node = current_node
            while node.parent is not None:
                path.append(node.action)
                node = node.parent
            path.reverse()
            return path, current_node.g_cost

        explored.add(current_node.state)
        
        if len(explored) % 10000 == 0:
            print(f"Explored {len(explored)} nodes... (Current path cost: {current_node.g_cost})")

        # Pass the current state and its g_cost to get successors
        for action, next_state in problem.get_successors(current_node.state, current_node.g_cost):
            child_node = Node(next_state, current_node, action, current_node.g_cost + 1)
            
            if child_node.state in explored:
                continue

            f_cost = child_node.g_cost + heuristic(next_state, problem)
            tie_breaker += 1
            heapq.heappush(frontier, (f_cost, tie_breaker, child_node))
                
    print("No solution found.")
    return None, 0
