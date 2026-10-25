import tkinter as tk
import random

# Game configuration
WIDTH = 600
HEIGHT = 600
CELL_SIZE = 20
DELAY = 150  # milliseconds

class SnakeGame:
    def __init__(self, master):
        self.master = master
        master.title("🐍 Snake")
        self.canvas = tk.Canvas(master, width=WIDTH, height=HEIGHT, bg='#2b2b2b')
        self.canvas.pack()

        # Score display
        self.score = 0
        self.score_label = tk.Label(master, text=f"Score: {self.score}", font=('Arial', 16), fg='white', bg='#2b2b2b')
        self.score_label.pack()

        # Game state
        self.snake = [(5, 5), (4, 5), (3, 5)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.food = self.place_food()
        self.running = False          # True when game is actively moving
        self.game_over = False
        self.god_mode = False
        self.konami_index = 0         # for tracking Konami code sequence
        self.konami_sequence = ['Up', 'Up', 'Down', 'Down', 'Left', 'Right', 'Left', 'Right', 'b', 'a']  # B and A are lowercase

        # Bind keyboard events
        master.bind('<Up>', lambda e: self.change_direction(0, -1))
        master.bind('<Down>', lambda e: self.change_direction(0, 1))
        master.bind('<Left>', lambda e: self.change_direction(-1, 0))
        master.bind('<Right>', lambda e: self.change_direction(1, 0))
        master.bind('<Key>', self.handle_key)  # catch all keys for WASD, Konami, O, Space

        # Draw initial screen
        self.draw()
        self.show_start_prompt()

    def show_start_prompt(self):
        """Display start prompt on canvas"""
        self.canvas.create_text(WIDTH//2, HEIGHT//2, text='Press SPACE to start',
                                font=('Arial', 24, 'bold'), fill='white')

    def place_food(self):
        """Place food randomly avoiding the snake"""
        while True:
            x = random.randint(0, WIDTH//CELL_SIZE - 1)
            y = random.randint(0, HEIGHT//CELL_SIZE - 1)
            if (x, y) not in self.snake:
                return (x, y)

    def change_direction(self, dx, dy):
        """Change snake direction, prevent immediate reverse"""
        if self.running and not self.game_over:
            if (dx, dy) != (-self.direction[0], -self.direction[1]):
                self.next_direction = (dx, dy)

    def handle_key(self, event):
        """Handle all key presses"""
        key = event.keysym

        # --- WASD movement ---
        if key == 'w' or key == 'W':
            self.change_direction(0, -1)
        elif key == 's' or key == 'S':
            self.change_direction(0, 1)
        elif key == 'a' or key == 'A':
            self.change_direction(-1, 0)
        elif key == 'd' or key == 'D':
            self.change_direction(1, 0)

        # --- Konami Code detection (only when game is active) ---
        if self.running and not self.game_over and not self.god_mode:
            # Convert keysym to lowercase for 'b' and 'a', keep Arrow keys as is
            if key in ['Up', 'Down', 'Left', 'Right']:
                seq_key = key
            elif key.lower() in ['b', 'a']:
                seq_key = key.lower()
            else:
                seq_key = None

            if seq_key:
             
                expected = self.konami_sequence[self.konami_index]
                if seq_key == expected:
                    self.konami_index += 1
                    if self.konami_index == len(self.konami_sequence):
                        self.activate_god_mode()
                else:
                   
            
                    self.konami_index = 0
                
                    if seq_key == self.konami_sequence[0]:
                        self.konami_index = 1

      
        if key.lower() == 'o' and self.god_mode and self.running:
            self.game_over = True
            self.running = False
            self.draw()  # will show game over

        
        if key == 'space':
            if not self.running and not self.game_over:
             
                self.running = True
                self.move_loop()
            elif self.game_over:
                
                self.restart()

    def activate_god_mode(self):
        """Turn on god mode"""
        self.god_mode = True
        self.konami_index = 0
        self.draw()  
      
        self.canvas.create_text(WIDTH//2, HEIGHT//2 - 50, text='✨ GOD MODE ON ✨',
                                font=('Arial', 24, 'bold'), fill='gold')
   
        self.master.after(2000, lambda: self.draw())  

    def restart(self):
        """Restart the game after game over"""
        self.snake = [(5, 5), (4, 5), (3, 5)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.food = self.place_food()
        self.score = 0
        self.running = True
        self.game_over = False
        self.god_mode = False
        self.konami_index = 0
        self.score_label.config(text=f"Score: {self.score}")
        self.canvas.delete('all')
        self.draw()
        self.move_loop()  # restart movement loop

    def move(self):
        """Move snake one step"""
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Wrap around if god mode and out of bounds
        if self.god_mode:
            new_head = (new_head[0] % (WIDTH//CELL_SIZE),
                        new_head[1] % (HEIGHT//CELL_SIZE))

        # Check if food eaten
        if new_head == self.food:
            self.snake.insert(0, new_head)
            self.score += 1
            self.score_label.config(text=f"Score: {self.score}")
            self.food = self.place_food()
            return True
        else:
            # Normal move
            self.snake.pop()
            self.snake.insert(0, new_head)
            return False

    def check_collision(self):
        """Check collision with walls or self"""
        head = self.snake[0]
        # Wall collision (only if not god mode, because god mode wraps)
        if not self.god_mode:
            if not (0 <= head[0] < WIDTH//CELL_SIZE and 0 <= head[1] < HEIGHT//CELL_SIZE):
                return True
        # Self collision (only if not god mode)
        if not self.god_mode:
            if head in self.snake[1:]:
                return True
        return False

    def draw(self):
        """Draw all game elements"""
        self.canvas.delete('all')

        # Grid
        for i in range(0, WIDTH, CELL_SIZE):
            self.canvas.create_line(i, 0, i, HEIGHT, fill='#3a3a3a')
        for j in range(0, HEIGHT, CELL_SIZE):
            self.canvas.create_line(0, j, WIDTH, j, fill='#3a3a3a')

        # Food 
        fx, fy = self.food
        x1 = fx * CELL_SIZE + 2
        y1 = fy * CELL_SIZE + 2
        x2 = x1 + CELL_SIZE - 4
        y2 = y1 + CELL_SIZE - 4
        self.canvas.create_oval(x1, y1, x2, y2, fill='#ff4444', outline='#ff8888', width=2)

        # Snake
        for i, (sx, sy) in enumerate(self.snake):
            x1 = sx * CELL_SIZE + 1
            y1 = sy * CELL_SIZE + 1
            x2 = x1 + CELL_SIZE - 2
            y2 = y1 + CELL_SIZE - 2
            if i == 0:
                color = '#66ff66'
                outline = '#88ff88'
            else:
                intensity = 50 + int(200 * (1 - i / len(self.snake)))
                color = f'#{intensity:02x}cc{intensity//2:02x}'
                outline = '#339933'
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline, width=1)

        # God mode indicator
        if self.god_mode:
            self.canvas.create_text(10, 10, text='GOD', anchor='nw',
                                    font=('Arial', 14, 'bold'), fill='gold')

 
        if self.game_over:
            self.canvas.create_text(WIDTH//2, HEIGHT//2 - 20, text='OVER',
                                    font=('Arial', 36, 'bold'), fill='red')
            self.canvas.create_text(WIDTH//2, HEIGHT//2 + 30, text='Press SPACE to restart',
                                    font=('Arial', 18), fill='white')

 
        if not self.running and not self.game_over:
            self.show_start_prompt()

    def move_loop(self):
        """Main game loop using after()"""
        if self.running and not self.game_over:
            
            self.direction = self.next_direction
            self.move()
            if self.check_collision():
                self.game_over = True
                self.running = False
                self.draw()
            else:
                self.draw()
                self.master.after(DELAY, self.move_loop)
        

def main():
    root = tk.Tk()
    game = SnakeGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()
