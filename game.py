import pygame

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
                pygame.K_SPACE: "Stop",
            }
            action = key_to_action.get(event.key)
            if action:
                self._apply_action(action)

    def _apply_action(self, action_name: str) -> bool:
        successors = dict(self.problem.get_successors(self.current_state, self.steps))
        next_state = successors.get(action_name)
        if not next_state:
            return False
        self.current_state = next_state
        self.steps += 1
        if self.problem.is_goal(self.current_state):
            print("You Win!")
            self.reset_game()
        return True

    # ------------------------------------------------------------------ Update
    def _update(self):
        if self.game_state == "AUTO_SEARCH":
            print("Finding optimal path using A*...")
            path, cost = solve_pacman_problem(self.problem)
            if path:
                self.solution_path = list(path)
                self.solution_cost = cost
                print(f"\n--- SOLUTION FOUND ---\nPath Cost: {cost}\nActions: {path}")
                self.game_state = "AUTO_ANIMATE"
            else:
                print("Could not find a solution.")
                self.game_state = "MENU"
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
        return self.problem.rotated_walls[self._current_rotation()]

    def _current_teleports(self):
        return self.problem.rotated_teleports[self._current_rotation()]

    def _current_exit(self):
        return self.problem.rotated_exit[self._current_rotation()]

    def _ghost_positions(self) -> set[tuple[int, int]]:
        rotation = self._current_rotation()
        return {
            _transform_pos(ghost.get_position(self.steps), rotation, self.problem.width, self.problem.height)
            for ghost in self.problem.ghosts
        }

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
                f"Manual | Steps: {self.steps} | Food: {len(self.current_state.food_left)}",
                (center_x, 15),
            )
        elif self.game_state == "AUTO_SEARCH":
            self._draw_text("Finding optimal path...", (center_x, self.window_size_h / 2))
        elif self.game_state == "AUTO_ANIMATE":
            self._draw_text(
                f"Auto | Steps: {self.steps}/{self.solution_cost} | Food: {len(self.current_state.food_left)}",
                (center_x, 15),
            )

    def _draw_text(self, text, position, color=(255, 255, 255)):
        text_surface = self.font.render(text, True, color)
        self.screen.blit(text_surface, text_surface.get_rect(center=position))
