import pygame
import threading

from pacman_problem import PacmanProblem, _transform_pos
from strategies import solve_pacman_problem


class PacmanGame:
    def __init__(self, layout_file: str):
        self.problem = PacmanProblem(self._load_layout(layout_file))
        self.tile_size = 20
        max_dim = max(self.problem.width, self.problem.height) * self.tile_size
        self.window_size_w = max_dim
        self.window_size_h = max_dim

        pygame.init()
        self.screen = pygame.display.set_mode((self.window_size_w, self.window_size_h))
        pygame.display.set_caption("Pac-Man A* Search (Rotating Maze)")
        self.font = pygame.font.Font(None, 24)

        self.reset_game()

    def _load_layout(self, filename: str):
        with open(filename, "r") as f:
            return [line.strip("\n") for line in f]

    # ------------------------------------------------------------------ Game loop
    def reset_game(self):
        self.game_state = "MENU"
        self.current_state = self.problem.get_initial_state()
        self.steps = 0  # g-cost / elapsed moves
        self.solution_path: list[str] = []
        self.solution_cost = 0
        self.animation_delay = 100
        self.last_move_time = 0
        # Async search state
        self._search_thread = None
        self._searching = False
        self._search_result = None  # tuple[list[str], int] | None

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle_input(event)
            self._update()
            self._draw()
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()

    def _handle_input(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if self.game_state == "MENU":
            if event.key == pygame.K_m:
                self.game_state = "MANUAL"
            elif event.key == pygame.K_a:
                self.game_state = "AUTO_SEARCH"
        elif self.game_state == "MANUAL":
            key_to_action = {
                pygame.K_UP: "North",
                pygame.K_DOWN: "South",
                pygame.K_LEFT: "West",
                pygame.K_RIGHT: "East",
            }
            action = key_to_action.get(event.key)
            if action:
                self._apply_action(action)
            else:
                # Teleport controls in MANUAL mode
                # - Press 'T' to use the first available teleport
                # - Press '1'..'4' to choose a specific teleport option when multiple exist
                teleport_keys = {pygame.K_t, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4}
                if event.key in teleport_keys:
                    # Ask the model for available teleport actions from this state
                    succ = dict(self.problem.get_successors(self.current_state, self.steps))
                    tp_actions = [k for k in succ.keys() if isinstance(k, str) and k.startswith("Teleport to ")]
                    # Fallback: if model didn't expose teleport actions but we're on a teleport tile,
                    # synthesize them from the rotated teleports set
                    if not tp_actions:
                        rotation = (self.current_state.step_mod_cycle // self.problem.ROTATION_PERIOD) % 4
                        teleports_here = self.problem.rotated_teleports[rotation]
                        if self.current_state.pos in teleports_here:
                            others = [t for t in teleports_here if t != self.current_state.pos]
                            tp_actions = [f"Teleport to {t}" for t in others]
                    if not tp_actions:
                        return
                    if event.key == pygame.K_t:
                        chosen = tp_actions[0]
                    else:
                        index = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}[event.key]
                        if index >= len(tp_actions):
                            return
                        chosen = tp_actions[index]
                    self._apply_action(chosen)

    def _apply_action(self, action_name: str) -> bool:
        # Precompute ghost positions for swap detection on this tick
        rotation_now = (self.current_state.step_mod_cycle // self.problem.ROTATION_PERIOD) % 4
        width_rot, height_rot = self.problem.rotated_dimensions[rotation_now]
        base_broken = getattr(self.current_state, "broken_walls", frozenset())
        ghosts_now = self.problem._ghost_positions_continuous(self.steps, rotation_now, base_broken)
        ghosts_next = self.problem._ghost_positions_continuous(self.steps + 1, rotation_now, base_broken)
        ghost_swaps = set(zip(ghosts_now, ghosts_next))

        # Compute intended target position (for manual arrows and auto replay)
        intended_pos = None
        if action_name in ("North", "South", "West", "East"):
            dx, dy = {"North": (0, -1), "South": (0, 1), "West": (-1, 0), "East": (1, 0)}[
                action_name
            ]
            intended_pos = (self.current_state.pos[0] + dx, self.current_state.pos[1] + dy)
        elif action_name.startswith("Teleport to "):
            try:
                intended_pos = eval(action_name.split(" to ")[1])
            except Exception:
                intended_pos = None

        successors = dict(self.problem.get_successors(self.current_state, self.steps))
        next_state = successors.get(action_name)
        if not next_state:
            # If the move was rejected by the model due to a ghost pass-through, treat as death
            if intended_pos is not None:
                # Swap-through collision
                if (intended_pos, self.current_state.pos) in ghost_swaps and self.current_state.pie_timer <= 0:
                    print("Game Over!")
                    self.reset_game()
                    return False
                # Direct step into a ghost's next tile should also be death when not powered
                if intended_pos in ghosts_next and self.current_state.pie_timer <= 0:
                    print("Game Over!")
                    self.reset_game()
                    return False
                # Direct step into a ghost's current tile should be death too when not powered
                if intended_pos in ghosts_now and self.current_state.pie_timer <= 0:
                    print("Game Over!")
                    self.reset_game()
                    return False
            return False
        self.current_state = next_state
        self.steps += 1

        # After applying the action, ensure Pac-Man is not sharing a tile with a ghost.
        rotation = (self.current_state.step_mod_cycle // self.problem.ROTATION_PERIOD) % 4
        width_rot, height_rot = self.problem.rotated_dimensions[rotation]
        base_broken = getattr(self.current_state, "broken_walls", frozenset())
        ghost_positions = set(self.problem._ghost_positions_continuous(self.steps, rotation, base_broken))
        if self.current_state.pos in ghost_positions:
            print("Game Over!")
            self.reset_game()
            return False

        if self.problem.is_goal(self.current_state):
            print("You Win!")
            self.reset_game()
        return True

    # ------------------------------------------------------------------ Update
    def _update(self):
        if self.game_state == "MANUAL":
            rotation = (self.current_state.step_mod_cycle // self.problem.ROTATION_PERIOD) % 4
            width_rot, height_rot = self.problem.rotated_dimensions[rotation]
            base_broken = getattr(self.current_state, "broken_walls", frozenset())
            ghost_positions = set(self.problem._ghost_positions_continuous(self.steps, rotation, base_broken))
            if self.current_state.pos in ghost_positions:
                print("Game Over!")
                self.reset_game()
        elif self.game_state == "AUTO_SEARCH":
            # Non-blocking: start the solver in a background thread and keep UI responsive
            if not self._searching:
                print("Finding optimal path using A* (async)...")
                self._searching = True
                self._search_result = None

                def _worker():
                    result = solve_pacman_problem(self.problem)
                    # Store result as (path, cost) or (None, 0)
                    self._search_result = result

                self._search_thread = threading.Thread(target=_worker, daemon=True)
                self._search_thread.start()
            else:
                # Poll for result
                if self._search_result is not None:
                    path, cost = self._search_result
                    if path:
                        self.solution_path = list(path)
                        self.solution_cost = cost
                        print(f"\n--- SOLUTION FOUND ---\nPath Cost: {cost}\nActions: {path}")
                        self.game_state = "AUTO_ANIMATE"
                    else:
                        print("Could not find a solution.")
                        self.game_state = "MENU"
                    # Reset search flags
                    self._searching = False
                    self._search_thread = None
        elif self.game_state == "AUTO_ANIMATE":
            current_time = pygame.time.get_ticks()
            if current_time - self.last_move_time > self.animation_delay:
                self.last_move_time = current_time
                if self.solution_path:
                    action = self.solution_path.pop(0)
                    if not self._apply_action(action):
                        print(f"Animation desynced on action '{action}'. Resetting.")
                        self.reset_game()
                else:
                    print("Animation finished.")
                    self.reset_game()

    # ------------------------------------------------------------------ Drawing helpers
    def _current_rotation(self) -> int:
        return (self.current_state.step_mod_cycle // self.problem.ROTATION_PERIOD) % 4

    def _current_dimensions(self) -> tuple[int, int]:
        return self.problem.rotated_dimensions[self._current_rotation()]

    def _current_walls(self):
        rotation = self._current_rotation()
        walls = set(self.problem.rotated_walls[rotation])
        # Remove any walls broken by Pac-Man (tracked in base coordinates)
        if hasattr(self.current_state, "broken_walls") and self.current_state.broken_walls:
            broken_rot = {
                _transform_pos(b, rotation, self.problem.width, self.problem.height)
                for b in self.current_state.broken_walls
            }
            walls -= broken_rot
        return walls

    def _current_teleports(self):
        return self.problem.rotated_teleports[self._current_rotation()]

    def _current_exit(self):
        return self.problem.rotated_exit[self._current_rotation()]

    def _ghost_positions(self) -> set[tuple[int, int]]:
        rotation = self._current_rotation()
        width_rot, height_rot = self.problem.rotated_dimensions[rotation]
        base_broken = getattr(self.current_state, "broken_walls", frozenset())
        return set(self.problem._ghost_positions_continuous(self.steps, rotation, base_broken))

    # ------------------------------------------------------------------ Rendering
    def _draw(self):
        self.screen.fill((0, 0, 0))

        rotation = self._current_rotation()
        width_rot, height_rot = self._current_dimensions()
        board_w = width_rot * self.tile_size
        board_h = height_rot * self.tile_size
        offset_x = (self.window_size_w - board_w) // 2
        offset_y = (self.window_size_h - board_h) // 2

        elements = [
            (self._current_walls(), "wall"),
            (self._current_teleports(), "teleport"),
            (self.current_state.food_left, "food"),
            (self.current_state.pies_left, "pie"),
            (self._ghost_positions(), "ghost"),
            ({self.current_state.pos}, "pacman"),
        ]
        exit_pos = self._current_exit()
        if exit_pos:
            elements.append(({exit_pos}, "exit"))

        for positions, elem_type in elements:
            for sx, sy in positions:
                rect = pygame.Rect(
                    offset_x + sx * self.tile_size,
                    offset_y + sy * self.tile_size,
                    self.tile_size,
                    self.tile_size,
                )
                if elem_type == "wall":
                    pygame.draw.rect(self.screen, (0, 0, 200), rect)
                elif elem_type == "teleport":
                    pygame.draw.rect(self.screen, (148, 0, 211), rect)
                elif elem_type == "food":
                    pygame.draw.circle(self.screen, (255, 255, 255), rect.center, 2)
                elif elem_type == "pie":
                    pygame.draw.circle(self.screen, (255, 182, 193), rect.center, 6)
                elif elem_type == "ghost":
                    pygame.draw.rect(self.screen, (255, 105, 180), rect)
                elif elem_type == "exit":
                    pygame.draw.rect(self.screen, (0, 255, 0), rect)
                elif elem_type == "pacman":
                    pac_color = (255, 255, 0) if self.current_state.pie_timer <= 0 else (255, 0, 0)
                    pygame.draw.circle(self.screen, pac_color, rect.center, self.tile_size // 2)

        center_x = self.window_size_w / 2
        if self.game_state == "MENU":
            self._draw_text("Press 'M' for Manual or 'A' for Auto Search", (center_x, self.window_size_h / 2))
        elif self.game_state == "MANUAL":
            self._draw_text(
                f"Manual | Steps: {self.steps} | Food: {len(self.current_state.food_left)} | Teleport: 'T' or '1-4'",
                (center_x, 15),
            )
        elif self.game_state == "AUTO_SEARCH":
            dots = "." * (1 + (pygame.time.get_ticks() // 500) % 3)
            self._draw_text(f"Finding optimal path{dots}", (center_x, self.window_size_h / 2))
        elif self.game_state == "AUTO_ANIMATE":
            self._draw_text(
                f"Auto | Steps: {self.steps}/{self.solution_cost} | Food: {len(self.current_state.food_left)}",
                (center_x, 15),
            )

    def _draw_text(self, text, position, color=(255, 255, 255)):
        text_surface = self.font.render(text, True, color)
        self.screen.blit(text_surface, text_surface.get_rect(center=position))
