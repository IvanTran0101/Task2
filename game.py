# game.py
# FINAL CORRECTED VERSION: Fixes the visual bug where pies did not disappear.

import pygame
from pacman_problem import PacmanProblem, _transform_pos
from strategies import solve_pacman_problem

class PacmanGame:
    def __init__(self, layout_file):
        self.problem = PacmanProblem(self._load_layout(layout_file))
        self.tile_size = 20
        self.window_size_w = self.problem.width * self.tile_size
        self.window_size_h = self.problem.height * self.tile_size
        
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_size_w, self.window_size_h))
        pygame.display.set_caption("Pac-Man A* Search (Optimal & Fast)")
        self.font = pygame.font.Font(None, 24)
        
        self.reset_game()

    def _load_layout(self, filename):
        with open(filename, 'r') as f:
            return [line.strip('\n') for line in f]

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                self._handle_input(event)
            self._update()
            self._draw()
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()

    def _handle_input(self, event):
        if event.type != pygame.KEYDOWN: return
        if self.game_state == "MENU":
            if event.key == pygame.K_m: self.game_state = "MANUAL"
            elif event.key == pygame.K_a: self.game_state = "AUTO_SEARCH"
        elif self.game_state == "MANUAL":
            key_map = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}
            if event.key in key_map:
                dx, dy = key_map[event.key]
                self._move_pacman_manual((self.pacman_pos[0] + dx, self.pacman_pos[1] + dy))

    def _move_pacman_manual(self, next_pos):
        current_walls = self.problem.walls[0]
        current_ghosts = {g.get_position(self.game_tick + 1) for g in self.problem.ghosts}
        if (next_pos in current_walls and self.pie_timer <= 0) or next_pos in current_ghosts: return
        self.steps += 1; self.pacman_pos = next_pos
        if self.pacman_pos in self.food: self.food.remove(self.pacman_pos)
        self.pie_timer = max(0, self.pie_timer - 1)
        if self.pacman_pos in self.pies: self.pie_timer = 5; self.pies.remove(self.pacman_pos)
        if not self.food and (not self.problem.exit or self.pacman_pos == self.problem.exit):
            print("You Win!"); self.reset_game()

    def reset_game(self):
        self.game_state = "MENU"
        self.pacman_pos = self.problem.initial_pacman_pos
        self.food = set(self.problem.initial_food)
        self.pies = set(self.problem.pies)
        self.pie_timer, self.steps, self.game_tick = 0, 0, 0
        self.solution_path, self.solution_cost = [], 0
        self.animation_delay, self.last_move_time = 100, 0

    def _update(self):
        if self.game_state == "MANUAL":
            self.game_tick += 1
            if self.pacman_pos in {g.get_position(self.game_tick) for g in self.problem.ghosts}:
                print("Game Over!"); self.reset_game()
        elif self.game_state == "AUTO_SEARCH":
            print("Finding optimal path using A*...")
            path, cost = solve_pacman_problem(self.problem)
            if path:
                self.solution_path, self.solution_cost = path, cost
                print(f"\n--- SOLUTION FOUND ---\nPath Cost: {cost}\nActions: {path}")
                self.game_state = "AUTO_ANIMATE"
            else:
                print("Could not find a solution."); self.game_state = "MENU"
        elif self.game_state == "AUTO_ANIMATE":
            current_time = pygame.time.get_ticks()
            if current_time - self.last_move_time > self.animation_delay:
                self.last_move_time = current_time
                if self.solution_path:
                    action = self.solution_path.pop(0); px, py = self.pacman_pos
                    if action == 'North': self.pacman_pos = (px, py - 1)
                    elif action == 'South': self.pacman_pos = (px, py + 1)
                    elif action == 'West': self.pacman_pos = (px - 1, py)
                    elif action == 'East': self.pacman_pos = (px + 1, py)
                    elif action.startswith('Teleport'): self.pacman_pos = eval(action.split(' to ')[1])
                    self.steps += 1
                    if self.pacman_pos in self.food: self.food.remove(self.pacman_pos)
                    self.pie_timer = max(0, self.pie_timer - 1)
                    # <<< START OF FIX: PIE REMOVAL >>>
                    if self.pacman_pos in self.pies:
                        self.pie_timer = 5
                        self.pies.remove(self.pacman_pos)
                    # <<< END OF FIX >>>
                else:
                    print("Animation finished."); self.reset_game()

    def _draw(self):
        self.screen.fill((0, 0, 0))
        ghost_time_source = self.game_tick if self.game_state == "MANUAL" else self.steps
        elements = [
            (self.problem.walls[0], 'wall'), (self.problem.teleports, 'teleport'),
            (self.food, 'food'), (self.pies, 'pie'),
            ({g.get_position(ghost_time_source) for g in self.problem.ghosts}, 'ghost'),
            ({self.pacman_pos}, 'pacman'),
        ]
        if self.problem.exit: elements.append(({self.problem.exit}, 'exit'))
        for positions, elem_type in elements:
            for sx, sy in positions:
                rect = pygame.Rect(sx * self.tile_size, sy * self.tile_size, self.tile_size, self.tile_size)
                if elem_type == 'wall': pygame.draw.rect(self.screen, (0, 0, 200), rect)
                elif elem_type == 'teleport': pygame.draw.rect(self.screen, (148, 0, 211), rect)
                elif elem_type == 'food': pygame.draw.circle(self.screen, (255, 255, 255), rect.center, 2)
                elif elem_type == 'pie': pygame.draw.circle(self.screen, (255, 182, 193), rect.center, 6)
                elif elem_type == 'ghost': pygame.draw.rect(self.screen, (255, 105, 180), rect)
                elif elem_type == 'exit': pygame.draw.rect(self.screen, (0, 255, 0), rect)
                elif elem_type == 'pacman':
                    pac_color = (255, 255, 0) if self.pie_timer <= 0 else (255, 0, 0)
                    pygame.draw.circle(self.screen, pac_color, rect.center, self.tile_size // 2)
        center_x = self.window_size_w / 2
        if self.game_state == "MENU": self._draw_text("Press 'M' for Manual or 'A' for Auto Search", (center_x, self.window_size_h/2))
        elif self.game_state == "MANUAL": self._draw_text(f"Manual | Steps: {self.steps} | Food: {len(self.food)}", (center_x, 15))
        elif self.game_state == "AUTO_SEARCH": self._draw_text("Finding optimal path...", (center_x, self.window_size_h/2))
        elif self.game_state == "AUTO_ANIMATE": self._draw_text(f"Auto | Steps: {self.steps}/{self.solution_cost} | Food: {len(self.food)}", (center_x, 15))

    def _draw_text(self, text, position, color=(255, 255, 255)):
        text_surface = self.font.render(text, True, color)
        self.screen.blit(text_surface, text_surface.get_rect(center=position))