import tkinter as tk
import math
import copy
import random

# ========== 配置 ==========
WORLD_W, WORLD_H = 1000, 700
WIN_W, WIN_H = 800, 500
SCALE = 1.8
PLAYER_SIZE = 8
ENEMY_SIZE = 8
BULLET_RADIUS = 3
KO_DURATION = 300
DELAY_FRAMES = 60
MINIMAP_RADIUS = 100
SNEAK_BEHIND_ANGLE = 45
BOX_ENTER_TIME = 10
CORPSE_DETECT_RADIUS = 60
PLAYER_MAX_HEALTH = 100
ENEMY_DAMAGE = 10
INVINCIBLE_FRAMES = 20

DEFAULT_KEYS = {
    'up': 'w', 'down': 's', 'left': 'a', 'right': 'd',
    'shoot': 'Button-1', 'sneak': 'Alt_L', 'interact': 'e', 'box': 'f'
}

BG_COLOR = '#2b2b2b'
WALL_COLOR = '#555555'
EXIT_COLOR = 'green'
PLAYER_COLOR = 'blue'
SNEAK_COLOR = 'cyan'
ENEMY_COLOR = 'red'
ENEMY_ALERT_COLOR = 'orange'
KO_COLOR = 'gray'
BULLET_COLOR = 'white'
PLAYER_BULLET_COLOR = 'yellow'
ENEMY_BULLET_COLOR = 'red'
CORPSE_COLOR = '#cc0000'
HEALTH_BAR_COLOR = '#00ff00'
HEALTH_BG_COLOR = '#333333'

# ========== 主菜单与设置（不变） ==========
class MainMenu:
    def __init__(self, master):
        self.master = master
        master.title("Stealth - Metal Gear")
        master.geometry("400x300")
        self.frame = tk.Frame(master)
        self.frame.pack(expand=True)
        tk.Label(self.frame, text="🐍 METAL GEAR STEALTH", font=('Arial', 20, 'bold')).pack(pady=20)
        tk.Button(self.frame, text="Start Game", font=('Arial', 14), command=self.start_game, width=15).pack(pady=10)
        tk.Button(self.frame, text="Key Settings", font=('Arial', 14), command=self.open_settings, width=15).pack(pady=10)
        tk.Button(self.frame, text="Quit", font=('Arial', 14), command=master.quit, width=15).pack(pady=10)
        self.keys = DEFAULT_KEYS.copy()

    def start_game(self):
        self.master.destroy()
        root_game = tk.Tk()
        game = Game(root_game, self.keys)
        root_game.mainloop()

    def open_settings(self):
        SettingsWindow(self.master, self.keys)

class SettingsWindow:
    def __init__(self, master, keys):
        self.keys = keys
        self.window = tk.Toplevel(master)
        self.window.title("Key Settings")
        self.window.geometry("370x520")
        self.window.transient(master)
        self.window.grab_set()
        tk.Label(self.window, text="Click a button, then press key or mouse.\nIf side button not recognized, click ✏️ and type e.g. Button-6",
                 font=('Arial', 9), justify=tk.LEFT).pack(pady=5)
        self.actions = {
            'up': 'Move Up', 'down': 'Move Down', 'left': 'Move Left', 'right': 'Move Right',
            'shoot': 'Shoot', 'sneak': 'Sneak (Hold)', 'interact': 'Interact', 'box': 'Enter/Exit Box'
        }
        self.buttons = {}
        for action, label in self.actions.items():
            frame = tk.Frame(self.window)
            frame.pack(pady=3)
            tk.Label(frame, text=f"{label}:", width=13, anchor='w').pack(side=tk.LEFT)
            btn = tk.Button(frame, text=self.keys[action], width=10, command=lambda a=action: self.rebind_key(a))
            btn.pack(side=tk.LEFT)
            self.buttons[action] = btn
            manual_btn = tk.Button(frame, text="✏️", width=2, command=lambda a=action: self.manual_entry(a))
            manual_btn.pack(side=tk.LEFT, padx=2)
        self.status_label = tk.Label(self.window, text="", fg="blue")
        self.status_label.pack(pady=5)
        tk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=10)

    def manual_entry(self, action):
        dialog = tk.Toplevel(self.window)
        dialog.title("Manual Key Entry")
        dialog.geometry("260x120")
        dialog.transient(self.window)
        dialog.grab_set()
        tk.Label(dialog, text=f"Enter key name for {self.actions[action]}:").pack(pady=5)
        entry = tk.Entry(dialog)
        entry.pack(pady=5)
        entry.insert(0, self.keys[action])
        def confirm():
            new_key = entry.get().strip()
            if new_key:
                self.keys[action] = new_key
                self.buttons[action].config(text=new_key)
                self.status_label.config(text=f"{self.actions[action]} set to {new_key}")
                dialog.destroy()
        tk.Button(dialog, text="OK", command=confirm).pack()

    def rebind_key(self, action):
        for btn in self.buttons.values():
            btn.config(state=tk.DISABLED)
        self.window.title(f"Press new key/mouse for {self.actions[action]}")
        self.status_label.config(text="Press any key or mouse button...")
        def on_input(event):
            key = None
            if hasattr(event, 'keysym') and event.keysym and event.keysym != '??':
                key = event.keysym
            elif hasattr(event, 'num'):
                key = f"Button-{event.num}"
                self.status_label.config(text=f"Mouse button {event.num} pressed")
            if key is None:
                return
            self.keys[action] = key
            self.buttons[action].config(text=key)
            self.status_label.config(text=f"{self.actions[action]} set to {key}")
            self.window.title("Key Settings")
            for btn in self.buttons.values():
                btn.config(state=tk.NORMAL)
            self.window.unbind('<Key>')
            self.window.unbind('<Button>')
            self.window.unbind('<ButtonPress>')
            self.window.unbind('<ButtonRelease>')
            return "break"
        self.window.bind('<Key>', on_input)
        self.window.bind('<Button>', on_input)
        self.window.bind('<ButtonPress>', on_input)
        self.window.bind('<ButtonRelease>', on_input)
        self.window.focus_set()

# ========== 子弹类 ==========
class Bullet:
    def __init__(self, x, y, vx, vy, speed, is_player=True):
        self.x = x; self.y = y; self.vx = vx * speed; self.vy = vy * speed
        self.life = 150; self.is_player = is_player; self.radius = BULLET_RADIUS
    def update(self):
        self.x += self.vx; self.y += self.vy; self.life -= 1
        return self.life > 0 and 0 <= self.x <= WORLD_W and 0 <= self.y <= WORLD_H

# ========== 敌人类（修复警觉bug） ==========
class Enemy:
    def __init__(self, x, y, patrol_points):
        self.x = x; self.y = y; self.size = ENEMY_SIZE
        self.patrol = patrol_points; self.target_idx = 0
        self.state = 'patrol'
        self.speed = 1.0; self.chase_speed = 2.0
        self.shoot_cooldown = 0
        self.ko_timer = 0; self.delay_timer = 0
        self.view_range = 100; self.view_angle = 60
        self.alert_level = 0; self.detect_player = False
        self.player_pos = None  # 保存玩家位置用于视野绘制

    def update(self, player, walls, all_bullets, corpses):
        # 保存玩家位置供绘制使用
        self.player_pos = player
        if self.state == 'dead': return
        if self.ko_timer > 0:
            self.ko_timer -= 1
            if self.ko_timer == 0:
                self.state = 'delay'
                self.delay_timer = DELAY_FRAMES
            return
        if self.delay_timer > 0:
            self.delay_timer -= 1
            if self.delay_timer == 0:
                self.state = 'patrol'
            return

        # 检测尸体
        for corpse in corpses:
            if not corpse.get('discovered', False):
                dist = math.hypot(self.x - corpse['x'], self.y - corpse['y'])
                if dist < CORPSE_DETECT_RADIUS:
                    corpse['discovered'] = True
                    if self.alert_level < 80:
                        self.alert_level = 80
                        self.state = 'chase'
                        self.detect_player = True

        dx = player[0] - self.x; dy = player[1] - self.y
        dist = math.hypot(dx, dy)
        angle_to_player = math.degrees(math.atan2(dy, dx))
        if self.state == 'patrol':
            target = self.patrol[self.target_idx]
            tx, ty = target
            dir_angle = math.degrees(math.atan2(ty - self.y, tx - self.x))
        else:
            # 使用传入的 player 而不是 self.player
            dir_angle = math.degrees(math.atan2(dy, dx))

        sight = False
        if dist < self.view_range and abs((angle_to_player - dir_angle) % 360) < self.view_angle/2:
            if not self.line_of_sight(player, walls):
                sight = True

        if sight:
            self.detect_player = True
            self.alert_level = min(100, self.alert_level + 1.0)
            if self.state not in ('chase','shoot'):
                self.state = 'chase'
        else:
            if self.alert_level > 0:
                self.alert_level = max(0, self.alert_level - 0.5)

        if self.state == 'patrol':
            target = self.patrol[self.target_idx]
            tx, ty = target
            d = math.hypot(tx - self.x, ty - self.y)
            if d < 3:
                self.target_idx = (self.target_idx + 1) % len(self.patrol)
            else:
                if d > 0:
                    self.x += ((tx - self.x) / d) * self.speed
                    self.y += ((ty - self.y) / d) * self.speed
        elif self.state == 'chase':
            if dist > 0:
                self.x += (dx / dist) * self.chase_speed
                self.y += (dy / dist) * self.chase_speed
            if dist < 200:
                self.state = 'shoot'
        elif self.state == 'shoot':
            if self.shoot_cooldown <= 0 and dist < 300:
                error = random.uniform(-0.1, 0.1)
                angle = math.atan2(dy, dx) + error
                speed = 3.0
                bullet = Bullet(self.x + self.size/2, self.y + self.size/2,
                                math.cos(angle), math.sin(angle), speed, is_player=False)
                all_bullets.append(bullet)
                self.shoot_cooldown = 30
            else:
                self.shoot_cooldown -= 1
            if dist > 300:
                self.state = 'chase'
            if not sight and self.alert_level < 30:
                self.state = 'patrol'
                self.detect_player = False

        self.x = max(0, min(WORLD_W - self.size, self.x))
        self.y = max(0, min(WORLD_H - self.size, self.y))

    def line_of_sight(self, player, walls):
        px, py = player
        steps = 10
        for i in range(steps):
            t = i / steps
            cx = self.x + self.size/2 + (px - self.x - self.size/2) * t
            cy = self.y + self.size/2 + (py - self.y - self.size/2) * t
            for (wx, wy, ww, wh) in walls:
                if wx < cx < wx+ww and wy < cy < wy+wh:
                    return False
        return True

    def draw(self, canvas, cx, cy, scale):
        if self.state == 'dead': return
        if self.state not in ('ko', 'delay', 'dead'):
            enemy_cx = (self.x + self.size/2 - cx) * scale
            enemy_cy = (self.y + self.size/2 - cy) * scale
            r = self.view_range * scale
            angle_start = -self.view_angle/2
            angle_end = self.view_angle/2
            pts = [(enemy_cx, enemy_cy)]
            # 使用保存的玩家位置或默认方向
            if self.player_pos is not None:
                dx = self.player_pos[0] - self.x
                dy = self.player_pos[1] - self.y
                dir_angle = math.atan2(dy, dx)
            else:
                dir_angle = 0
            for deg in range(int(angle_start), int(angle_end)+1):
                rad = math.radians(deg) + dir_angle
                pts.append((enemy_cx + r*math.cos(rad), enemy_cy + r*math.sin(rad)))
            color = ENEMY_COLOR if self.state == 'patrol' else ENEMY_ALERT_COLOR
            canvas.create_polygon(pts, fill=color, stipple='gray50', outline='')

        ex, ey = (self.x - cx) * scale, (self.y - cy) * scale
        ex2, ey2 = ex + self.size*scale, ey + self.size*scale
        if self.ko_timer > 0:
            color = KO_COLOR
        elif self.delay_timer > 0:
            color = '#666666'
        elif self.state in ('chase','shoot'):
            color = ENEMY_ALERT_COLOR
        else:
            color = ENEMY_COLOR
        canvas.create_rectangle(ex, ey, ex2, ey2, fill=color, outline='darkred')
        if self.ko_timer > 0:
            z_count = self.ko_timer // 100
            z_text = 'Z' * min(z_count, 3)
            canvas.create_text(ex + self.size*scale//2, ey - 10, text=z_text, fill='white', font=('Arial', 10))
        if self.delay_timer > 0:
            canvas.create_text(ex + self.size*scale//2, ey - 10, text='?', fill='orange', font=('Arial', 12))

# ========== 游戏主类 ==========
class Game:
    def __init__(self, master, keys):
        self.master = master
        master.title("Stealth - Metal Gear Demo")
        self.canvas = tk.Canvas(master, width=WIN_W, height=WIN_H, bg=BG_COLOR)
        self.canvas.pack()

        self.keys = keys
        self.init_player()
        self.init_world()
        self.init_enemies()

        self.bullets = []
        self.shoot_cooldown = 0
        self.mouse_x = WIN_W//2; self.mouse_y = WIN_H//2
        self.mouse_world_x = 0; self.mouse_world_y = 0
        self.camera = [0.0, 0.0]
        self.key_state = {}
        self.global_alert = 0.0

        # 玩家血量
        self.player_health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.invincible_timer = 0

        # 纸箱
        self.in_box = False
        self.box_entering = False
        self.box_deploy_timer = 0
        self.box_x = 0; self.box_y = 0
        self.box_size = 20

        # 尸体
        self.corpses = []

        # 处决状态
        self.executing = False
        self.execution_type = None
        self.execution_timer = 0
        self.execution_phase = 0
        self.execution_target = None
        self.execution_choice = 'ko'
        self.execution_confirmed = False
        self.execution_elapsed = 0.0
        self.execution_progress = 0.0
        self.box_shake = 0
        self.enemy_original_pos = None
        self.player_original_pos = None
        self.player_shake_offset = (0,0)
        self.enemy_shake_offset = (0,0)
        self.slide_velocity = 0.0
        self.knockback_angle = 0
        self.stun_timer = 0
        self.enemy_head_icon = ''
        self.enemy_head_timer = 0

        # 受伤闪红
        self.damage_flash_timer = 0

        master.bind('<KeyPress>', self.key_press)
        master.bind('<KeyRelease>', self.key_release)
        master.bind('<Button>', self.mouse_press)
        master.bind('<ButtonRelease>', self.mouse_release)
        master.bind('<Motion>', self.mouse_move)
        master.bind('<r>', self.restart)
        master.focus_set()

        self.update()
        self.draw()

    def init_player(self):
        self.player = [100.0, 100.0]
        self.player_dir = (1.0, 0.0)
        self.speed = 2.0; self.sneak_speed = 1.2
        self.is_sneaking = False
        self.game_over = False; self.win = False

    def init_enemies(self):
        patrols = [[(200,150),(350,150),(350,250),(200,250)], [(600,400),(750,400),(750,500)]]
        starts = [(200,150), (600,400)]
        self.enemies = []
        for i, start in enumerate(starts):
            e = Enemy(start[0], start[1], patrols[i])
            self.enemies.append(e)

    def init_world(self):
        self.exit_x, self.exit_y = 880.0, 580.0
        self.exit_size = 12
        self.walls = [(150,80,30,150), (400,50,20,120), (600,200,120,15),
                      (300,400,40,100), (750,150,20,150), (500,500,80,20)]

    # ---------- 事件处理 ----------
    def key_press(self, e):
        self.key_state[e.keysym] = True
        if e.keysym == self.keys['interact']:
            if self.executing and self.execution_phase >= 3:
                self.execution_confirmed = True
                self.finish_execution(True)
            else:
                self.interact()
        if e.keysym == self.keys['box'] and not self.executing:
            self.toggle_box()
        if e.keysym in ('a', 'A'):
            self.execution_choice = 'kill'
        if e.keysym in ('d', 'D'):
            self.execution_choice = 'ko'

    def key_release(self, e):
        self.key_state[e.keysym] = False

    def mouse_press(self, e):
        btn_key = f"Button-{e.num}"
        self.key_state[btn_key] = True
        if btn_key == self.keys['shoot'] and not self.executing:
            self.shoot()

    def mouse_release(self, e):
        btn_key = f"Button-{e.num}"
        self.key_state[btn_key] = False

    def mouse_move(self, e):
        self.mouse_x = e.x; self.mouse_y = e.y
        self.mouse_world_x = self.mouse_x/SCALE + self.camera[0]
        self.mouse_world_y = self.mouse_y/SCALE + self.camera[1]
        dx = self.mouse_world_x - (self.player[0] + PLAYER_SIZE/2)
        dy = self.mouse_world_y - (self.player[1] + PLAYER_SIZE/2)
        length = math.hypot(dx, dy)
        if length > 0.1:
            self.player_dir = (dx/length, dy/length)

    # ---------- 交互 ----------
    def interact(self):
        if self.executing: return
        if self.in_box:
            for e in self.enemies:
                if e.state == 'dead': continue
                if math.hypot(self.player[0]-e.x, self.player[1]-e.y) < 30:
                    self.start_execution(e, 'box')
                    break
        else:
            if self.is_sneaking:
                for e in self.enemies:
                    if e.state in ('dead','ko','delay'): continue
                    dx = e.x - self.player[0]; dy = e.y - self.player[1]
                    if math.hypot(dx, dy) < 20:
                        if e.state == 'patrol':
                            target = e.patrol[e.target_idx]
                            enemy_dir = (target[0]-e.x, target[1]-e.y)
                        else:
                            enemy_dir = (self.player[0]-e.x, self.player[1]-e.y)
                        enemy_angle = math.degrees(math.atan2(enemy_dir[1], enemy_dir[0]))
                        player_angle = math.degrees(math.atan2(self.player_dir[1], self.player_dir[0]))
                        if abs((enemy_angle - player_angle) % 360) < SNEAK_BEHIND_ANGLE:
                            self.start_execution(e, 'outside')
                            break

    def toggle_box(self):
        if self.in_box:
            self.exit_box()
        else:
            if not self.box_entering:
                self.box_entering = True
                self.box_deploy_timer = BOX_ENTER_TIME
                self.box_x = self.player[0]
                self.box_y = self.player[1]

    def enter_box(self):
        self.in_box = True
        self.box_entering = False
        self.box_deploy_timer = 0

    def exit_box(self):
        self.in_box = False

    # ---------- 处决系统 ----------
    def start_execution(self, enemy, exec_type):
        if self.executing: return
        self.executing = True
        self.execution_type = exec_type
        self.execution_target = enemy
        self.execution_choice = 'ko'
        self.execution_confirmed = False
        self.execution_elapsed = 0.0
        self.execution_progress = 0.0
        self.enemy_head_icon = ''
        self.box_shake = 0

        if exec_type == 'box':
            self.enemy_original_pos = (enemy.x, enemy.y)
            enemy.state = 'grabbed'
            self.execution_phase = 1
            self.execution_timer = 8
            self.enemy_head_icon = '?'
        else:
            self.enemy_original_pos = (enemy.x, enemy.y)
            self.player_original_pos = (self.player[0], self.player[1])
            enemy.state = 'grabbed'
            self.execution_phase = 3
            self.execution_timer = 40
            self.execution_elapsed = 0.0
            self.player_shake_offset = (0,0)
            self.enemy_shake_offset = (0,0)

    def update_execution(self):
        if not self.executing: return
        dt = 0.05
        self.execution_elapsed += dt
        self.execution_progress = min(1.0, self.execution_elapsed / 7.0)

        if self.execution_type == 'box':
            if self.execution_phase == 1:
                self.execution_timer -= 1
                if self.execution_timer <= 0:
                    self.execution_phase = 2
                    self.execution_timer = 4
                    self.enemy_head_icon = '!'
            elif self.execution_phase == 2:
                self.execution_timer -= 1
                if self.execution_timer <= 0:
                    self.execution_phase = 3
                    self.execution_target.x = self.box_x + self.box_size/2 - self.execution_target.size/2
                    self.execution_target.y = self.box_y + self.box_size/2 - self.execution_target.size/2
                    self.box_shake = 10
                    self.execution_elapsed = 0.0
                    self.execution_progress = 0.0
            elif self.execution_phase == 3:
                if self.box_shake > 0:
                    self.box_shake -= 0.5
                if self.execution_progress >= 1.0 and not self.execution_confirmed:
                    self.finish_execution(False)
        else:
            if self.execution_phase == 3:
                self.execution_timer -= 1
                if self.execution_timer <= 0:
                    self.execution_phase = 4
                self.player_shake_offset = (random.uniform(-3,3), random.uniform(-3,3))
                self.enemy_shake_offset = (random.uniform(-3,3), random.uniform(-3,3))
                if self.execution_progress >= 1.0 and not self.execution_confirmed:
                    self.finish_execution(False)
            else:
                self.player_shake_offset = (0,0)
                self.enemy_shake_offset = (0,0)
                if self.execution_progress >= 1.0 and not self.execution_confirmed:
                    self.finish_execution(False)

    def finish_execution(self, success):
        if not self.executing: return
        target = self.execution_target
        if success and self.execution_confirmed:
            if self.execution_choice == 'kill':
                target.state = 'dead'
                self.corpses.append({
                    'x': target.x + target.size/2,
                    'y': target.y + target.size/2,
                    'discovered': False
                })
                self.global_alert = min(100, self.global_alert + 10)
            else:
                target.state = 'ko'
                target.ko_timer = KO_DURATION
                self.global_alert = min(100, self.global_alert + 5)
        else:
            if self.execution_type == 'box':
                target.state = 'patrol'
                target.alert_level = 99.99
                target.detect_player = True
                self.global_alert = 99.99
                target.x = self.box_x + self.box_size + 5
                target.y = self.box_y + self.box_size/2 - target.size/2
            else:
                target.state = 'patrol'
                target.alert_level = 99.99
                target.detect_player = True
                self.global_alert = 99.99
                dx = self.player[0] - target.x
                dy = self.player[1] - target.y
                length = math.hypot(dx, dy)
                if length > 0:
                    self.knockback_angle = math.atan2(dy, dx)
                    self.slide_velocity = 5.0
                self.stun_timer = 10

        self.executing = False
        self.execution_target = None
        self.enemy_head_icon = ''
        self.box_shake = 0
        self.player_shake_offset = (0,0)
        self.enemy_shake_offset = (0,0)

    # ---------- 射击 ----------
    def shoot(self):
        if self.shoot_cooldown > 0 or self.game_over or self.win or self.in_box or self.executing:
            return
        dx, dy = self.player_dir
        bullet = Bullet(self.player[0]+PLAYER_SIZE/2, self.player[1]+PLAYER_SIZE/2,
                        dx, dy, 6.0, is_player=True)
        self.bullets.append(bullet)
        self.shoot_cooldown = 10

    # ---------- 玩家受伤 ----------
    def take_damage(self, amount):
        if self.invincible_timer > 0:
            return
        self.player_health -= amount
        self.damage_flash_timer = 5
        self.invincible_timer = INVINCIBLE_FRAMES
        if self.player_health <= 0:
            self.player_health = 0
            self.game_over = True

    # ---------- 更新 ----------
    def update(self):
        if not self.game_over and not self.win:
            if self.executing:
                self.update_execution()
            else:
                self.move_player()
                self.update_bullets()
                self.update_enemies()
                self.check_collisions()
                self.check_win()
                if self.shoot_cooldown > 0:
                    self.shoot_cooldown -= 1

                if self.box_entering:
                    self.box_deploy_timer -= 1
                    if self.box_deploy_timer <= 0:
                        self.enter_box()

                if self.global_alert > 0:
                    self.global_alert = max(0, self.global_alert - 0.005)

                if self.slide_velocity > 0.1:
                    self.player[0] += math.cos(self.knockback_angle) * self.slide_velocity
                    self.player[1] += math.sin(self.knockback_angle) * self.slide_velocity
                    self.slide_velocity *= 0.95
                    if self.slide_velocity < 0.1:
                        self.slide_velocity = 0
                        self.stun_timer = 10
                if self.stun_timer > 0:
                    self.stun_timer -= 1

                if self.invincible_timer > 0:
                    self.invincible_timer -= 1
                if self.damage_flash_timer > 0:
                    self.damage_flash_timer -= 1

        self.camera[0] = self.player[0] + PLAYER_SIZE/2 - WIN_W/(2*SCALE)
        self.camera[1] = self.player[1] + PLAYER_SIZE/2 - WIN_H/(2*SCALE)

        self.draw()
        self.master.after(50, self.update)

    def move_player(self):
        if self.executing or self.slide_velocity > 0.1 or self.stun_timer > 0:
            return
        if self.in_box:
            speed = self.sneak_speed
        else:
            self.is_sneaking = self.key_state.get(self.keys['sneak'], False)
            speed = self.sneak_speed if self.is_sneaking else self.speed

        dx = dy = 0
        if self.key_state.get(self.keys['up'], False): dy = -1
        if self.key_state.get(self.keys['down'], False): dy = 1
        if self.key_state.get(self.keys['left'], False): dx = -1
        if self.key_state.get(self.keys['right'], False): dx = 1
        if dx != 0 and dy != 0:
            dx *= 0.707; dy *= 0.707

        new_x = self.player[0] + dx * speed
        new_y = self.player[1] + dy * speed
        new_x = max(0, min(WORLD_W - PLAYER_SIZE, new_x))
        new_y = max(0, min(WORLD_H - PLAYER_SIZE, new_y))
        if not self.check_wall_collision(new_x, new_y, PLAYER_SIZE, PLAYER_SIZE):
            self.player[0] = new_x
            self.player[1] = new_y
            if self.box_entering:
                self.box_x = new_x; self.box_y = new_y
            if self.in_box:
                self.box_x = new_x; self.box_y = new_y

    def check_wall_collision(self, x, y, w, h):
        for (wx, wy, ww, wh) in self.walls:
            if (x < wx+ww and x+w > wx and y < wy+wh and y+h > wy):
                return True
        return False

    def update_enemies(self):
        for e in self.enemies:
            if e.state != 'grabbed':
                e.update(self.player, self.walls, self.bullets, self.corpses)
                if e.detect_player:
                    self.global_alert = min(100, self.global_alert + 0.5)
                    if e.alert_level > 80:
                        self.global_alert = 99.99

    def update_bullets(self):
        for b in self.bullets[:]:
            if not b.update():
                self.bullets.remove(b); continue
            hit_wall = False
            for (wx, wy, ww, wh) in self.walls:
                if (b.x > wx and b.x < wx+ww and b.y > wy and b.y < wy+wh):
                    hit_wall = True; break
            if hit_wall:
                self.bullets.remove(b); continue
            if b.is_player:
                for e in self.enemies:
                    if e.state == 'dead' or e.state == 'grabbed': continue
                    if (abs(b.x-(e.x+e.size/2)) < e.size/2+b.radius and
                        abs(b.y-(e.y+e.size/2)) < e.size/2+b.radius):
                        e.state = 'ko'; e.ko_timer = KO_DURATION
                        self.bullets.remove(b); break
            else:
                if (abs(b.x-(self.player[0]+PLAYER_SIZE/2)) < PLAYER_SIZE/2+b.radius and
                    abs(b.y-(self.player[1]+PLAYER_SIZE/2)) < PLAYER_SIZE/2+b.radius):
                    self.take_damage(ENEMY_DAMAGE)
                    self.bullets.remove(b)
        # 子弹擦过
        for b in self.bullets:
            if b.is_player:
                for e in self.enemies:
                    if e.state in ('dead','ko','delay','grabbed'): continue
                    dist = math.hypot(b.x-(e.x+e.size/2), b.y-(e.y+e.size/2))
                    if dist < 30 and dist > e.size/2+b.radius:
                        e.alert_level = min(100, e.alert_level + 30)
                        self.global_alert = min(100, self.global_alert + 30)

    def check_collisions(self):
        for e in self.enemies:
            if e.state in ('dead','ko','delay','grabbed'): continue
            if (abs(self.player[0]-e.x) < PLAYER_SIZE+e.size and
                abs(self.player[1]-e.y) < PLAYER_SIZE+e.size):
                if not self.in_box and self.invincible_timer == 0:
                    self.take_damage(ENEMY_DAMAGE)
                    dx = e.x - self.player[0]
                    dy = e.y - self.player[1]
                    length = math.hypot(dx, dy)
                    if length > 0:
                        e.x += (dx/length) * 20
                        e.y += (dy/length) * 20

    def check_win(self):
        if (abs(self.player[0]-self.exit_x) < PLAYER_SIZE+self.exit_size and
            abs(self.player[1]-self.exit_y) < PLAYER_SIZE+self.exit_size):
            self.win = True

    # ---------- 绘制 ----------
    def draw(self):
        self.canvas.delete('all')
        cx, cy = self.camera

        def to_screen(wx, wy):
            return (wx - cx)*SCALE, (wy - cy)*SCALE

        # 背景
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill=BG_COLOR, outline='')
        # 墙壁
        for (wx, wy, ww, wh) in self.walls:
            x1,y1=to_screen(wx,wy); x2,y2=to_screen(wx+ww,wy+wh)
            self.canvas.create_rectangle(x1,y1,x2,y2,fill=WALL_COLOR,outline='#777777')
        # 出口
        x1,y1=to_screen(self.exit_x,self.exit_y)
        x2,y2=to_screen(self.exit_x+self.exit_size,self.exit_y+self.exit_size)
        self.canvas.create_rectangle(x1,y1,x2,y2,fill=EXIT_COLOR,outline='lightgreen')
        px,py=to_screen(self.exit_x+3,self.exit_y)
        self.canvas.create_line(px,py,px,py-12*SCALE,fill='white',width=2)

        # 尸体
        for corpse in self.corpses:
            x,y=to_screen(corpse['x'], corpse['y'])
            size = 6 * SCALE
            self.canvas.create_line(x-size, y-size, x+size, y+size, fill=CORPSE_COLOR, width=2)
            self.canvas.create_line(x+size, y-size, x-size, y+size, fill=CORPSE_COLOR, width=2)

        # 敌人
        for e in self.enemies:
            if e.state == 'grabbed': continue
            e.draw(self.canvas, cx, cy, SCALE)

        # 处决特殊绘制
        if self.executing and self.execution_target:
            if self.execution_type == 'box' and self.execution_phase in (1,2):
                ex, ey = self.execution_target.x, self.execution_target.y
                sx, sy = to_screen(ex, ey)
                self.canvas.create_text(sx+ENEMY_SIZE*SCALE//2, sy-15,
                                        text=self.enemy_head_icon, fill='yellow', font=('Arial', 20))
            if self.execution_type == 'outside' and self.execution_phase == 3:
                px, py = to_screen(self.player[0]+self.player_shake_offset[0], self.player[1]+self.player_shake_offset[1])
                p_size=PLAYER_SIZE*SCALE
                self.canvas.create_rectangle(px,py,px+p_size,py+p_size,fill=PLAYER_COLOR,outline='white')
                ex, ey = to_screen(self.execution_target.x+self.enemy_shake_offset[0],
                                   self.execution_target.y+self.enemy_shake_offset[1])
                self.canvas.create_rectangle(ex,ey,ex+ENEMY_SIZE*SCALE,ey+ENEMY_SIZE*SCALE,
                                             fill=ENEMY_ALERT_COLOR,outline='darkred')

        # 子弹
        for b in self.bullets:
            x,y=to_screen(b.x,b.y); r=b.radius*SCALE
            color = PLAYER_BULLET_COLOR if b.is_player else ENEMY_BULLET_COLOR
            self.canvas.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='lightgray')

        # 纸箱
        if self.box_entering or self.in_box:
            x,y=to_screen(self.box_x,self.box_y)
            size=self.box_size*SCALE
            shake = 0
            if self.box_shake > 0:
                shake = int(self.box_shake)
            self.canvas.create_rectangle(x+shake, y+shake, x+size+shake, y+size+shake,
                                         fill='#8B4513', outline='#D2691E', width=2)
            self.canvas.create_text(x+size//2+shake, y+size//2+shake, text='📦', font=('Arial', int(size/2)))

        # 玩家（非抖动时）
        if not (self.executing and self.execution_type == 'outside' and self.execution_phase == 3):
            if not self.in_box:
                if self.invincible_timer > 0 and self.invincible_timer % 10 < 5:
                    pass  # 闪烁
                else:
                    px, py = to_screen(self.player[0], self.player[1])
                    p_size=PLAYER_SIZE*SCALE
                    p_color=SNEAK_COLOR if self.is_sneaking else PLAYER_COLOR
                    self.canvas.create_rectangle(px,py,px+p_size,py+p_size,fill=p_color,outline='white')
                    cx_p=px+p_size/2; cy_p=py+p_size/2
                    dir_len=15*SCALE; dx,dy=self.player_dir
                    self.canvas.create_line(cx_p,cy_p,cx_p+dx*dir_len,cy_p+dy*dir_len,fill='yellow',width=2)

        # ---- 血条（左下角） ----
        bar_width = 150
        bar_height = 14
        bar_x = 15
        bar_y = WIN_H - 30
        self.canvas.create_rectangle(bar_x, bar_y, bar_x+bar_width, bar_y+bar_height,
                                     fill=HEALTH_BG_COLOR, outline='white')
        health_ratio = self.player_health / self.max_health
        fill_width = int(bar_width * health_ratio)
        color = f'#{int(255*(1-health_ratio)):02x}{int(255*health_ratio):02x}00'
        self.canvas.create_rectangle(bar_x, bar_y, bar_x+fill_width, bar_y+bar_height,
                                     fill=color, outline='')
        self.canvas.create_text(bar_x + bar_width//2, bar_y + bar_height//2,
                                text=f"HP {self.player_health}/{self.max_health}",
                                fill='white', font=('Arial', 9, 'bold'))

        # ---- 警觉值（右上角） ----
        alert_text = f"ALERT: {int(self.global_alert)}%"
        self.canvas.create_text(WIN_W - 15, 15, text=alert_text, anchor='ne',
                                fill='orange' if self.global_alert > 50 else 'white',
                                font=('Arial', 14, 'bold'))

        # 受伤闪红（半透明用 stipple）
        if self.damage_flash_timer > 0:
            self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill='#ff0000', stipple='gray50', outline='')

        # 其他状态
        status = "SNEAK" if self.is_sneaking else "NORMAL"
        if self.in_box: status = "IN BOX"
        if self.executing: status = "EXECUTING..."
        self.canvas.create_text(10, 10, text=status, anchor='nw',
                                fill='white', font=('Arial', 12))
        self.canvas.create_text(WIN_W-10, 35, text="[LMB]Shoot [E]Interact [F]Box [R]Restart",
                                anchor='ne', fill='gray', font=('Arial', 10))

        # 处决UI
        if self.executing and self.execution_phase >= 3:
            self.draw_execution_ui()

        # 小地图
        self.draw_minimap()

        # 覆盖层
        if self.game_over:
            self.canvas.create_rectangle(0,0,WIN_W,WIN_H,fill='black',stipple='gray50')
            self.canvas.create_text(WIN_W//2,WIN_H//2-20,text='GAME OVER',fill='red',font=('Arial',30,'bold'))
            self.canvas.create_text(WIN_W//2,WIN_H//2+30,text='Press R to restart',fill='white',font=('Arial',16))
        elif self.win:
            self.canvas.create_rectangle(0,0,WIN_W,WIN_H,fill='black',stipple='gray50')
            self.canvas.create_text(WIN_W//2,WIN_H//2-20,text='✨ MISSION COMPLETE ✨',fill='green',font=('Arial',30,'bold'))
            self.canvas.create_text(WIN_W//2,WIN_H//2+30,text='Press R to restart',fill='white',font=('Arial',16))

    def draw_execution_ui(self):
        cx = WIN_W - 100
        cy = WIN_H // 2
        radius = 60
        self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                outline='white', fill='#333333', width=2)
        self.canvas.create_text(cx-40, cy, text="KILL", fill='red' if self.execution_choice=='kill' else 'gray',
                                font=('Arial', 12, 'bold'))
        self.canvas.create_text(cx+40, cy, text="KO", fill='blue' if self.execution_choice=='ko' else 'gray',
                                font=('Arial', 12, 'bold'))
        if self.execution_choice == 'kill':
            self.canvas.create_line(cx-50, cy-15, cx-30, cy, cx-50, cy+15, fill='yellow', width=2)
        else:
            self.canvas.create_line(cx+50, cy-15, cx+30, cy, cx+50, cy+15, fill='yellow', width=2)

        progress = self.execution_progress
        start_angle = -90
        extent = progress * 360
        color = f'#{int(255*progress):02x}{int(255*(1-progress)):02x}00'
        self.canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                               start=start_angle, extent=extent, outline=color, width=4, style=tk.ARC)
        remaining = max(0, 7.0 - self.execution_elapsed)
        self.canvas.create_text(cx, cy, text=f"{remaining:.1f}s", fill='white', font=('Arial', 12))
        if not self.execution_confirmed:
            self.canvas.create_text(cx, cy+radius+15, text="Press E to confirm", fill='yellow', font=('Arial', 10))

    # ---------- 小地图 ----------
    def draw_minimap(self):
        center_x, center_y = MINIMAP_RADIUS+10, MINIMAP_RADIUS+10
        self.canvas.create_oval(center_x-MINIMAP_RADIUS, center_y-MINIMAP_RADIUS,
                                center_x+MINIMAP_RADIUS, center_y+MINIMAP_RADIUS,
                                fill='#000000', outline='white', width=2, stipple='gray50')
        scale_x = (2*MINIMAP_RADIUS)/WORLD_W
        scale_y = (2*MINIMAP_RADIUS)/WORLD_H
        scale = min(scale_x, scale_y)*0.9
        def world_to_minimap(wx, wy):
            mx = wx*scale; my = wy*scale
            offset_x = center_x - (WORLD_W/2)*scale
            offset_y = center_y - (WORLD_H/2)*scale
            return mx+offset_x, my+offset_y

        for (wx, wy, ww, wh) in self.walls:
            x1,y1=world_to_minimap(wx,wy); x2,y2=world_to_minimap(wx+ww,wy+wh)
            self.canvas.create_rectangle(x1,y1,x2,y2,fill='#888888',outline='')

        for e in self.enemies:
            if e.state == 'dead': continue
            ex, ey = e.x+e.size/2, e.y+e.size/2
            mx, my = world_to_minimap(ex, ey)
            if math.hypot(mx-center_x, my-center_y) < MINIMAP_RADIUS-2:
                color = KO_COLOR if e.ko_timer>0 else ENEMY_COLOR
                self.canvas.create_oval(mx-3,my-3,mx+3,my+3,fill=color,outline='')

        for corpse in self.corpses:
            mx, my = world_to_minimap(corpse['x'], corpse['y'])
            if math.hypot(mx-center_x, my-center_y) < MINIMAP_RADIUS-2:
                self.canvas.create_oval(mx-2,my-2,mx+2,my+2,fill='#ff6666',outline='')

        ex, ey = self.exit_x+self.exit_size/2, self.exit_y+self.exit_size/2
        mx, my = world_to_minimap(ex, ey)
        if math.hypot(mx-center_x, my-center_y) < MINIMAP_RADIUS-2:
            self.canvas.create_oval(mx-4,my-4,mx+4,my+4,fill=EXIT_COLOR,outline='white')
        px, py = world_to_minimap(self.player[0]+PLAYER_SIZE/2, self.player[1]+PLAYER_SIZE/2)
        dx = mx-px; dy = my-py
        length = math.hypot(dx, dy)
        if length > 0.1:
            scale_arrow = min(1.0, (MINIMAP_RADIUS-5)/length)
            end_x = px + dx*scale_arrow; end_y = py + dy*scale_arrow
            self.canvas.create_line(px,py,end_x,end_y,fill='gold',width=2,dash=(3,2))
            angle = math.atan2(dy, dx)
            tip_len=6
            wing1=(end_x-tip_len*0.7*math.cos(angle-math.radians(45)),
                   end_y-tip_len*0.7*math.sin(angle-math.radians(45)))
            wing2=(end_x-tip_len*0.7*math.cos(angle+math.radians(45)),
                   end_y-tip_len*0.7*math.sin(angle+math.radians(45)))
            self.canvas.create_polygon(end_x,end_y,wing1[0],wing1[1],wing2[0],wing2[1],
                                       fill='gold',outline='gold')
        self.canvas.create_oval(center_x-MINIMAP_RADIUS, center_y-MINIMAP_RADIUS,
                                center_x+MINIMAP_RADIUS, center_y+MINIMAP_RADIUS,
                                outline='white', width=2)

    def restart(self, event=None):
        self.init_player()
        self.init_enemies()
        self.bullets.clear()
        self.shoot_cooldown = 0
        self.global_alert = 0
        self.player_health = PLAYER_MAX_HEALTH
        self.invincible_timer = 0
        self.damage_flash_timer = 0
        self.in_box = False
        self.box_entering = False
        self.box_deploy_timer = 0
        self.executing = False
        self.execution_target = None
        self.execution_confirmed = False
        self.enemy_head_icon = ''
        self.box_shake = 0
        self.slide_velocity = 0
        self.stun_timer = 0
        self.corpses.clear()
        self.draw()

# ========== 启动 ==========
if __name__ == "__main__":
    root = tk.Tk()
    menu = MainMenu(root)
    root.mainloop()
