# main.py
# The main entry point for the Pac-Man A* project.

import sys
import os # Import the 'os' module to check for file existence
from game import PacmanGame

if __name__ == '__main__':
    # --- MODIFIED LOGIC ---

    DEFAULT_MAP = "task02_pacman_default_map.txt"
    
    # Check for a command-line argument first. This is the highest priority.
    if len(sys.argv) > 1:
        layout_file = sys.argv[1]
        print(f"Using map file from command line: '{layout_file}'")
    
    # If no command-line arg, check if the example map exists.
    elif os.path.exists("task02_pacman_example_map.txt"):
        layout_file = "task02_pacman_example_map.txt"
        print(f"No command line argument. Found and using '{layout_file}'.")

    # If neither of the above, create and use the default map.
    else:
        layout_file = DEFAULT_MAP
        print(f"No map file provided or found. Creating and using default map '{layout_file}'.")
        default_map_content = """
                                %%%%%%%%%%%%%%%%%%%%%%%%%%%%
                                % P G. . . . . . . . . .G  %
                                % . %%%%%%% % %%%%%%% % .  %
                                % . % O % . . . % O % . .  %
                                % . %   % %%%%% %   % . .  %
                                % . % . . . . . . . % . .  %
                                % . %%%%%%%%%%%%%%% % . .  %
                                % . . . . . .E. . . . . .  %
                                %%%%%%%%%%%%%%%%%%%%%%%%%%%%
                            """.strip()
        try:
            with open(layout_file, "w") as f:
                f.write(default_map_content)
        except IOError as e:
            print(f"Error creating default map file: {e}")
            sys.exit(1)

    # --- END OF MODIFIED LOGIC ---

    try:
        # Create and run the game instance
        game_instance = PacmanGame(layout_file)
        game_instance.run()
    except FileNotFoundError:
        print(f"Error: The map file '{layout_file}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")