import cv2
import mediapipe as mp
import math
import random
import time
import os
import numpy as np
from src.DataManager import DataManager
from src.Components import Button, VirtualKeyboard

# ==========================================
# 3. MAIN GAME CLASS
# ==========================================
class HandGame:
    def __init__(self):
        # --- Window Setup (Fullscreen) ---
        self.window_name = "Hand Game Ultimate"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        # --- Camera Setup ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)
        
        success, img = self.cap.read()
        if success:
            self.height, self.width, _ = img.shape
        else:
            self.width = 1280
            self.height = 720
            
        self.center = (self.width // 2, self.height // 2)
        
        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

        # --- Data & System ---
        self.db = DataManager()
        
        # --- Game State ---
        self.running = True
        self.state = "LOGIN" 
        self.current_user = None
        self.is_guest = False 
        self.current_difficulty = "NORMAL"
        
        # --- Gesture Logic ---
        self.hand_clicked_status = {} 
        self.pinch_threshold = 40
        self.enable_special_enemies = False 

        # ===============================================================
        # [NEW] LOAD SPECIFIC ASSETS
        # ===============================================================
        self.icons_pinch = self.load_images_from_folder("src/icons/pinch")
        self.icons_fist = self.load_images_from_folder("src/icons/fist")
        
        # Load Default Ship
        self.img_ship_default = self.load_single_image("src/icons/spaceship/spaceship.png")
        
        # Load Special Assets
        self.img_enemy_special = self.load_single_image("src/icons/special/special_enemy.png")
        self.img_ship_evolved = self.load_single_image("src/icons/special/special_ship.png")

        # State to track which ship to draw
        self.current_ship_img = self.img_ship_default 

        # --- UI Initialization ---
        self.init_ui_elements()

        self.enemies = []
        self.score = 0
        self.difficulty_settings = {}
        self.set_difficulty("NORMAL") 

    def init_ui_elements(self):
        """Calculates dynamic UI positions based on screen size."""
        W, H = self.width, self.height
        cx = W // 2  
        cy = H // 2  
        
        # Dynamic Sizes
        btn_w = int(W * 0.2) 
        btn_h = int(H * 0.08) 
        btn_size = (btn_w, btn_h)
        
        self.keyboard = VirtualKeyboard(int(W * 0.3), int(H * 0.3))
        
        # --- 1. LOGIN SCREEN ---
        self.btn_skip = Button("SKIP (GUEST)", (W - btn_w - 20, H - btn_h - 20), size=btn_size, color=(150, 200, 255))
        
        # --- 2. CONFIRM / DIALOGS ---
        self.btn_confirm_yes = Button("CONFIRM", (cx - btn_w - 10, cy + 50), size=btn_size, color=(150, 255, 150))
        self.btn_confirm_no = Button("GO BACK", (cx + 10, cy + 50), size=btn_size, color=(255, 150, 150))
        self.btn_delete_yes = Button("YES, DELETE", (cx - btn_w - 10, cy + 50), size=btn_size, color=(255, 100, 100))
        self.btn_delete_no = Button("NO, GO BACK", (cx + 10, cy + 50), size=btn_size, color=(150, 255, 150))

        # --- 3. MENU SCREEN ---
        # [MODIFIED] Removed "CHANGE SHIP" button layout
        start_y = int(H * 0.35)
        step_y = int(H * 0.12)
        self.btn_start = Button("START GAME", (cx - btn_w//2, start_y), size=btn_size)
        self.btn_records = Button("RECORDS", (cx - btn_w//2, start_y + step_y), size=btn_size)
        self.btn_exit = Button("EXIT", (cx - btn_w//2, start_y + step_y * 2), size=btn_size)

        # --- 4. DIFFICULTY SCREEN ---
        gap = int(W * 0.05)
        total_w = 3 * btn_w + 2 * gap
        start_x = (W - total_w) // 2
        diff_y = int(H * 0.4)
        
        self.btn_easy = Button("EASY", (start_x, diff_y), size=btn_size, color=(150, 255, 150))
        self.btn_med = Button("NORMAL", (start_x + btn_w + gap, diff_y), size=btn_size, color=(150, 150, 255))
        self.btn_hard = Button("HARD", (start_x + 2*(btn_w + gap), diff_y), size=btn_size, color=(150, 150, 150))
        
        self.btn_special_toggle = Button("SPECIAL: OFF", (cx - btn_w//2, diff_y + step_y), size=btn_size, color=(200, 200, 200))
        self.btn_back = Button("BACK", (cx - btn_w//2, H - btn_h - 30), size=btn_size)

        # --- 5. RECORDS SCREEN ---
        self.btn_back_rec = Button("BACK", (W - btn_w - 30, H - btn_h - 30), size=btn_size)
        self.btn_delete_user = Button("DELETE USER", (30, H - btn_h - 30), size=btn_size, color=(100, 100, 255))
        self.btn_switch_user = Button("SWITCH USER", (cx - btn_w//2, H - btn_h - 30), size=btn_size, color=(255, 255, 150))
        self.btn_add_user = Button("ADD USER", (cx - btn_w//2, H - btn_h * 2 - 50), size=btn_size, color=(200, 255, 200))
        self.btn_back_to_record_kb = Button("BACK", (30, H - btn_h - 30), size=btn_size, color=(255, 100, 100))

        # --- 6. SWITCH USER ---
        self.user_buttons = []
        self.btn_back_from_switch = Button("BACK", (cx - btn_w//2, H - btn_h - 20), size=btn_size)

        # --- 7. PAUSE OVERLAY ---
        pause_size = int(W * 0.06)
        self.btn_pause = Button("II", (W - pause_size - 20, 20), size=(pause_size, int(pause_size*0.8)), color=(255, 255, 200))
        
        p_y = int(H * 0.35)
        self.btn_resume = Button("RESUME", (cx - btn_w//2, p_y), size=btn_size, color=(150, 255, 150))
        self.btn_restart = Button("RESTART", (cx - btn_w//2, p_y + step_y), size=btn_size, color=(255, 255, 150))
        self.btn_save_quit = Button("SAVE & QUIT", (cx - btn_w//2, p_y + step_y * 2), size=btn_size, color=(255, 150, 150))

    def load_images_from_folder(self, folder):
        """Loads all images from a folder into a list."""
        images = []
        if not os.path.exists(folder): return []
        for filename in os.listdir(folder):
            try:
                img = cv2.imread(os.path.join(folder, filename), cv2.IMREAD_UNCHANGED)
                if img is not None: images.append(img)
            except: pass
        return images

    def load_single_image(self, path):
        """Loads a single image safely."""
        if os.path.exists(path):
            return cv2.imread(path, cv2.IMREAD_UNCHANGED)
        return None

    def refresh_user_buttons(self):
        users = self.db.get_user_list()
        self.user_buttons = []
        W, H = self.width, self.height
        margin_x = int(W * 0.1)
        margin_y = int(H * 0.2)
        btn_w = int(W * 0.25)
        btn_h = int(H * 0.1)
        gap_x = 20
        gap_y = 20
        cols = max(1, (W - 2 * margin_x) // (btn_w + gap_x))
        
        for i, u_name in enumerate(users):
            row = i // cols
            col = i % cols
            x = margin_x + col * (btn_w + gap_x)
            y = margin_y + row * (btn_h + gap_y)
            if i < 12:
                self.user_buttons.append(Button(u_name, (x, y), size=(btn_w, btn_h)))

    def set_difficulty(self, level):
        self.current_difficulty = level 
        if level == "EASY":
            self.difficulty_settings = {"spawn_rate": 1.5, "speed_base": 2, "speed_mult": 0.05}
        elif level == "NORMAL":
            self.difficulty_settings = {"spawn_rate": 1.0, "speed_base": 4, "speed_mult": 0.1}
        elif level == "HARD":
            self.difficulty_settings = {"spawn_rate": 0.6, "speed_base": 6, "speed_mult": 0.2}
        self.spawn_interval = self.difficulty_settings["spawn_rate"]

    def spawn_enemy(self):
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top': x, y = random.randint(0, self.width), 0
        elif side == 'bottom': x, y = random.randint(0, self.width), self.height
        elif side == 'left': x, y = 0, random.randint(0, self.height)
        else: x, y = self.width, random.randint(0, self.height)
        
        angle = math.atan2(self.center[1] - y, self.center[0] - x)
        speed = self.difficulty_settings["speed_base"] + (self.score * self.difficulty_settings["speed_mult"])
        
        enemy_type = 'circle'
        enemy_color = (0, 0, 255)
        icon_img = None

        # =================================================
        # [NEW] BOSS SPAWN LOGIC
        # Condition: Hard Mode + Score >= 64 + 90% Chance
        # =================================================
        spawned_boss = False
        
        if self.current_difficulty == "EASY" and np.log2(self.score) == np.floor(np.log2(self.score)):
            chance = 1
            # chance = np.log2(self.score)/50
            if random.random() < chance: # 90% chance
                enemy_type = 'boss'
                enemy_color = (0, 255, 255) # Yellowish fallback
                icon_img = self.img_enemy_special
                spawned_boss = True
                print("DEBUG: BOSS SPAWNED!")


        # If not boss, do standard logic
        if not spawned_boss:
            # Special "Square" Enemy Logic (Toggle based)
            is_special_square = False
            chance = 0.0
            if self.enable_special_enemies:
                if self.current_difficulty == "HARD": chance = 0.5 
                elif self.current_difficulty == "NORMAL": chance = 0.3
                else: chance = 0.1
                
                if random.random() < chance:
                    is_special_square = True
                    enemy_type = 'square'
                    enemy_color = (255, 0, 0)

            # Assign Icon for standard types
            if is_special_square and self.icons_fist:
                icon_img = random.choice(self.icons_fist)
            elif not is_special_square and self.icons_pinch:
                icon_img = random.choice(self.icons_pinch)

        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'radius': int(self.width * 0.04) if enemy_type == 'boss' else int(self.width * 0.035),
            'color': enemy_color,
            'type': enemy_type,
            'icon': icon_img
        })

    # [HELPER] Draw transparent PNG
    def draw_image_centered(self, bg_img, icon, x, y, diameter):
        if icon is None: return
        if diameter <= 0: return 
        try:
            icon_resized = cv2.resize(icon, (diameter, diameter))
        except: return

        h, w, _ = icon_resized.shape
        y1, y2 = y - h // 2, y + h // 2
        x1, x2 = x - w // 2, x + w // 2

        if y1 < 0 or y2 > bg_img.shape[0] or x1 < 0 or x2 > bg_img.shape[1]: return 

        if icon_resized.shape[2] == 4:
            alpha_s = icon_resized[:, :, 3] / 255.0
            alpha_l = 1.0 - alpha_s
            for c in range(0, 3):
                bg_img[y1:y2, x1:x2, c] = (alpha_s * icon_resized[:, :, c] +
                                           alpha_l * bg_img[y1:y2, x1:x2, c])
        else:
            bg_img[y1:y2, x1:x2] = icon_resized

    def detect_fist_logic(self, img, hand_lms):
        h, w, _ = img.shape
        wrist = hand_lms.landmark[0]
        finger_tips = [8, 12, 16, 20]
        total_dist = 0
        for tip_id in finger_tips:
            tip = hand_lms.landmark[tip_id]
            dist = math.hypot(tip.x * w - wrist.x * w, tip.y * h - wrist.y * h)
            total_dist += dist
        middle_mcp = hand_lms.landmark[9]
        cx, cy = int(middle_mcp.x * w), int(middle_mcp.y * h)
        threshold = h * 0.6 
        is_fist = total_dist < threshold
        return is_fist, (cx, cy)

    def detect_pinch_logic(self, img, hand_lms, hand_id):
        h, w, _ = img.shape
        thumb = hand_lms.landmark[4]
        index = hand_lms.landmark[8]
        x4, y4 = int(thumb.x * w), int(thumb.y * h)
        x8, y8 = int(index.x * w), int(index.y * h)
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2
        length = math.hypot(x8 - x4, y8 - y4)

        is_clicking = False
        state_locked = self.hand_clicked_status.get(hand_id, False)

        if length < self.pinch_threshold:
            if not state_locked:
                is_clicking = True
                self.hand_clicked_status[hand_id] = True
        else:
            self.hand_clicked_status[hand_id] = False
            
        cursor_data = {
            "pos": (cx, cy),
            "p1": (x4, y4),
            "p2": (x8, y8),
            "is_pinching": length < self.pinch_threshold
        }
        return is_clicking, cursor_data

    def run(self):
        while self.running: 
            success, img = self.cap.read()
            if not success: break
            
            img = cv2.flip(img, 1)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            all_clicks = []      
            all_cursors_data = [] 
            cursor_positions = [] 
            all_fists = [] 
            
            if results.multi_hand_landmarks:
                for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                    clicked, cursor_data = self.detect_pinch_logic(img, hand_lms, idx)
                    all_cursors_data.append((hand_lms, cursor_data))
                    cursor_positions.append(cursor_data["pos"])
                    if clicked:
                        all_clicks.append(cursor_data["pos"])
                    
                    is_fist, fist_pos = self.detect_fist_logic(img, hand_lms)
                    if is_fist:
                        all_fists.append(fist_pos)

            overlay = img.copy()

            # --- STATE LOGIC ---
            if self.state == "LOGIN":
                cv2.putText(img, "PLEASE ENTER NAME", (int(self.width*0.3), int(self.height*0.15)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.keyboard.draw(img, overlay, cursor_positions) 
                self.btn_skip.draw_on_overlay(overlay, any(self.btn_skip.is_hovering(*c) for c in cursor_positions))

                for click_pos in all_clicks:
                    res = self.keyboard.handle_click(click_pos)
                    if res == "ENTER_PRESSED":
                        self.next_state_after_confirm = "LOGIN_SUCCESS"
                        self.state = "CONFIRM_ACTION"
                    if self.btn_skip.is_hovering(*click_pos):
                        self.current_user = "Guest"
                        self.is_guest = True
                        self.state = "MENU"

            elif self.state == "ADD_USER_INPUT":
                cv2.putText(img, "CREATE NEW USER", (int(self.width*0.3), int(self.height*0.15)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.keyboard.draw(img, overlay, cursor_positions)
                self.btn_back_to_record_kb.draw_on_overlay(overlay, any(self.btn_back_to_record_kb.is_hovering(*c) for c in cursor_positions))

                for click_pos in all_clicks:
                    res = self.keyboard.handle_click(click_pos)
                    if res == "ENTER_PRESSED":
                        self.next_state_after_confirm = "ADD_SUCCESS"
                        self.state = "CONFIRM_ACTION"
                    if self.btn_back_to_record_kb.is_hovering(*click_pos):
                        self.state = "RECORDS"

            elif self.state == "CONFIRM_ACTION":
                box_x1, box_x2 = int(self.width * 0.25), int(self.width * 0.75)
                box_y1, box_y2 = int(self.height * 0.3), int(self.height * 0.7)
                cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (255, 255, 255), -1)
                cv2.putText(img, f"Confirm: '{self.keyboard.input_text}'?", (box_x1 + 20, box_y1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)

                for btn in [self.btn_confirm_yes, self.btn_confirm_no]:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover)

                for click_pos in all_clicks:
                    if self.btn_confirm_yes.is_hovering(*click_pos):
                        self.current_user = self.keyboard.input_text
                        self.is_guest = False
                        self.db.register_user(self.current_user)
                        if self.next_state_after_confirm == "LOGIN_SUCCESS": self.state = "MENU"
                        elif self.next_state_after_confirm == "ADD_SUCCESS": self.state = "RECORDS"
                    elif self.btn_confirm_no.is_hovering(*click_pos):
                        if self.next_state_after_confirm == "LOGIN_SUCCESS": self.state = "LOGIN"
                        elif self.next_state_after_confirm == "ADD_SUCCESS": self.state = "ADD_USER_INPUT"

            elif self.state == "CONFIRM_DELETE":
                box_x1, box_x2 = int(self.width * 0.2), int(self.width * 0.8)
                box_y1, box_y2 = int(self.height * 0.3), int(self.height * 0.7)
                cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (200, 200, 255), -1)
                cv2.putText(img, "ARE YOU SURE?", (box_x1 + 50, box_y1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)

                for btn in [self.btn_delete_yes, self.btn_delete_no]:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover)
                for click_pos in all_clicks:
                    if self.btn_delete_yes.is_hovering(*click_pos):
                        self.db.delete_user(self.current_user)
                        self.keyboard.input_text = ""
                        self.state = "LOGIN" 
                    elif self.btn_delete_no.is_hovering(*click_pos):
                        self.state = "RECORDS" 

            elif self.state == "MENU":
                display_name = "Guest" if self.is_guest else self.current_user
                cv2.putText(img, f"Welcome, {display_name}", (int(self.width*0.05), int(self.height*0.1)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                
                # [MODIFIED] Removed "CHANGE SHIP" button
                for btn in [self.btn_start, self.btn_records, self.btn_exit]:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover) 
                
                for click_pos in all_clicks:
                    if self.btn_start.is_hovering(*click_pos): self.state = "DIFFICULTY"
                    elif self.btn_records.is_hovering(*click_pos): self.state = "RECORDS"
                    elif self.btn_exit.is_hovering(*click_pos): self.running = False

            elif self.state == "DIFFICULTY":
                cv2.putText(img, "SELECT DIFFICULTY", (int(self.width * 0.35), int(self.height*0.2)), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)
                self.btn_special_toggle.text = f"SPECIAL: {'ON' if self.enable_special_enemies else 'OFF'}"
                self.btn_special_toggle.color = (150, 255, 150) if self.enable_special_enemies else (200, 200, 200)

                buttons = [self.btn_easy, self.btn_med, self.btn_hard, self.btn_back, self.btn_special_toggle]
                for btn in buttons:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover)
                
                for click_pos in all_clicks:
                    if self.btn_easy.is_hovering(*click_pos):
                        self.set_difficulty("EASY")
                        self.state = "PLAYING"
                        self.current_ship_img = self.img_ship_default # Reset Ship
                    elif self.btn_med.is_hovering(*click_pos):
                        self.set_difficulty("NORMAL")
                        self.state = "PLAYING"
                        self.current_ship_img = self.img_ship_default # Reset Ship
                    elif self.btn_hard.is_hovering(*click_pos):
                        self.set_difficulty("HARD")
                        self.state = "PLAYING"
                        self.current_ship_img = self.img_ship_default # Reset Ship
                    elif self.btn_back.is_hovering(*click_pos):
                        self.state = "MENU"
                    elif self.btn_special_toggle.is_hovering(*click_pos):
                        self.enable_special_enemies = not self.enable_special_enemies
                    
                    if self.state == "PLAYING":
                        self.enemies = []
                        self.score = 0
                        self.last_spawn_time = time.time()

            elif self.state == "PLAYING":
                # [NEW] Draw Current Player Ship (Default or Evolved)
                if self.current_ship_img is not None:
                    self.draw_image_centered(img, self.current_ship_img, self.center[0], self.center[1], 80)
                else:
                    cv2.circle(img, self.center, 30, (0, 255, 0), -1)

                cv2.putText(img, f"Score: {self.score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2)
                cv2.putText(img, f"Diff: {self.current_difficulty}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
                if self.is_guest:
                     cv2.putText(img, "GUEST MODE", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

                is_hover_pause = any(self.btn_pause.is_hovering(*c) for c in cursor_positions)
                self.btn_pause.draw_on_overlay(overlay, is_hover_pause)

                for click_pos in all_clicks:
                    if self.btn_pause.is_hovering(*click_pos):
                        self.state = "PAUSED"

                if time.time() - self.last_spawn_time > self.spawn_interval:
                    self.spawn_enemy()
                    self.last_spawn_time = time.time()
                
                for enemy in self.enemies[:]:
                    enemy['x'] += enemy['vx']
                    enemy['y'] += enemy['vy']
                    
                    hit_enemy = False
                    
                    # 1. Circle Enemy -> Pinch
                    if enemy['type'] == 'circle':
                        for click_pos in all_clicks:
                            if math.hypot(enemy['x'] - click_pos[0], enemy['y'] - click_pos[1]) < (enemy['radius'] + 30):
                                self.enemies.remove(enemy)
                                self.score += 1
                                hit_enemy = True
                                break 
                    
                    # 2. Square/Boss Enemy -> Fist
                    elif enemy['type'] == 'square' or enemy['type'] == 'boss':
                        for fist_pos in all_fists:
                             if math.hypot(enemy['x'] - fist_pos[0], enemy['y'] - fist_pos[1]) < (enemy['radius'] + 40): 
                                
                                # [NEW] Boss Transformation Logic
                                if enemy['type'] == 'boss':
                                    self.score += 10
                                    # Transform Ship!
                                    if self.img_ship_evolved is not None:
                                        self.icons_pinch = self.load_images_from_folder("src/icons/special_pinch")
                                        self.icons_fist = self.load_images_from_folder("src/icons/special_fist")
                                        self.current_ship_img = self.img_ship_evolved
                                    print("BOSS DEFEATED! SHIP EVOLVED!")
                                else:
                                    self.score += 2
                                    
                                self.enemies.remove(enemy)
                                hit_enemy = True
                                break

                    if hit_enemy: continue

                    if math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1]) < 40:
                        self.state = "GAME_OVER"
                        if not self.is_guest:
                            self.db.add_score(self.current_user, self.score, self.current_difficulty)
                    
                    draw_x, draw_y = int(enemy['x']), int(enemy['y'])
                    
                    if enemy.get('icon') is not None:
                        self.draw_image_centered(img, enemy['icon'], draw_x, draw_y, int(enemy['radius']*2))
                    else:
                        # Fallback shapes
                        if enemy['type'] == 'circle':
                            cv2.circle(img, (draw_x, draw_y), int(enemy['radius']), enemy['color'], -1)
                        elif enemy['type'] == 'boss':
                            # Boss fallback if image missing: Big Yellow Circle
                            cv2.circle(img, (draw_x, draw_y), int(enemy['radius']), (0, 255, 255), -1)
                            cv2.circle(img, (draw_x, draw_y), int(enemy['radius']), (255, 255, 255), 4)
                        else:
                            r = int(enemy['radius'])
                            cv2.rectangle(img, (draw_x-r, draw_y-r), (draw_x+r, draw_y+r), enemy['color'], -1)
                            cv2.rectangle(img, (draw_x-r, draw_y-r), (draw_x+r, draw_y+r), (255, 255, 255), 2)

            elif self.state == "PAUSED":
                bx1, bx2 = int(self.width*0.3), int(self.width*0.7)
                by1, by2 = int(self.height*0.2), int(self.height*0.8)
                cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (200, 200, 200), -1)
                cv2.putText(img, "PAUSED", (bx1 + 100, by1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
                
                buttons = [self.btn_resume, self.btn_restart, self.btn_save_quit]
                for btn in buttons:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover)
                for click_pos in all_clicks:
                    if self.btn_resume.is_hovering(*click_pos): self.state = "PLAYING"
                    elif self.btn_restart.is_hovering(*click_pos):
                        self.enemies = []
                        self.score = 0
                        self.last_spawn_time = time.time()
                        self.state = "PLAYING"
                        self.current_ship_img = self.img_ship_default # Reset Ship
                    elif self.btn_save_quit.is_hovering(*click_pos):
                        if not self.is_guest: self.db.add_score(self.current_user, self.score, self.current_difficulty)
                        self.state = "MENU"

            elif self.state == "GAME_OVER":
                cv2.rectangle(overlay, (0,0), (self.width, self.height), (0,0,0), -1)
                cv2.putText(img, "GAME OVER", (int(self.width*0.35), int(self.height*0.4)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                cv2.putText(img, f"Final Score: {self.score}", (int(self.width*0.4), int(self.height*0.5)), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                self.btn_back.draw_on_overlay(overlay, any(self.btn_back.is_hovering(*c) for c in cursor_positions))
                for click_pos in all_clicks:
                    if self.btn_back.is_hovering(*click_pos): self.state = "MENU"

            elif self.state == "RECORDS":
                cv2.rectangle(overlay, (100, 100), (self.width - 100, self.height - 50), (240, 240, 240), -1)
                cv2.putText(img, "PLAYER RECORDS", (int(self.width*0.35), 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (50, 50, 50), 3)
                if self.is_guest:
                    cv2.putText(img, "Guest User - No Records", (int(self.width*0.3), 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (100,100,100), 2)
                    buttons_to_draw = [self.btn_back_rec, self.btn_switch_user, self.btn_add_user]
                else:
                    user_data = self.db.data.get(self.current_user, {})
                    y_offset = 200
                    cv2.putText(img, f"User: {self.current_user}", (150, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                    y_offset += 50
                    for diff in ["EASY", "NORMAL", "HARD"]:
                        d_data = user_data.get(diff, {"best_score": 0, "history": []})
                        text = f"{diff} - Best: {d_data['best_score']} | Games: {len(d_data['history'])}"
                        cv2.putText(img, text, (150, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,100,0), 2)
                        y_offset += 40
                    buttons_to_draw = [self.btn_back_rec, self.btn_delete_user, self.btn_switch_user, self.btn_add_user]
                for btn in buttons_to_draw:
                    btn.draw_on_overlay(overlay, any(btn.is_hovering(*c) for c in cursor_positions))
                for click_pos in all_clicks:
                    if self.btn_back_rec.is_hovering(*click_pos): self.state = "MENU"
                    elif not self.is_guest and self.btn_delete_user.is_hovering(*click_pos): self.state = "CONFIRM_DELETE" 
                    elif self.btn_switch_user.is_hovering(*click_pos):
                        self.refresh_user_buttons()
                        self.state = "SWITCH_USER_SELECT"
                    elif self.btn_add_user.is_hovering(*click_pos):
                        self.keyboard.input_text = ""
                        self.state = "ADD_USER_INPUT"

            elif self.state == "SWITCH_USER_SELECT":
                cv2.rectangle(overlay, (50, 50), (self.width-50, self.height-50), (240, 240, 240), -1)
                cv2.putText(img, "SELECT USER", (int(self.width*0.4), 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
                for btn in self.user_buttons:
                    btn.draw_on_overlay(overlay, any(btn.is_hovering(*c) for c in cursor_positions))
                self.btn_back_from_switch.draw_on_overlay(overlay, any(self.btn_back_from_switch.is_hovering(*c) for c in cursor_positions))
                for click_pos in all_clicks:
                    for btn in self.user_buttons:
                        if btn.is_hovering(*click_pos):
                            self.current_user = btn.text
                            self.is_guest = False
                            self.state = "MENU" 
                            break
                    if self.btn_back_from_switch.is_hovering(*click_pos): self.state = "RECORDS"

            # --- STEP 3: COMPOSITING ---
            alpha = 0.3 
            if self.state == "GAME_OVER": alpha = 0.6
            elif self.state == "PAUSED": alpha = 0.4 
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

            # --- STEP 4: DRAW TEXT LAYERS ---
            if self.state == "LOGIN": 
                self.keyboard.draw_text(img)
                self.btn_skip.draw_text_and_border(img)
            elif self.state == "ADD_USER_INPUT":
                self.keyboard.draw_text(img)
                self.btn_back_to_record_kb.draw_text_and_border(img)
            elif self.state == "CONFIRM_ACTION":
                self.btn_confirm_yes.draw_text_and_border(img)
                self.btn_confirm_no.draw_text_and_border(img)
            elif self.state == "CONFIRM_DELETE":
                self.btn_delete_yes.draw_text_and_border(img)
                self.btn_delete_no.draw_text_and_border(img)
            elif self.state == "MENU": 
                # [MODIFIED] Removed "Change Ship"
                for btn in [self.btn_start, self.btn_records, self.btn_exit]: btn.draw_text_and_border(img)
            elif self.state == "DIFFICULTY":
                for btn in [self.btn_easy, self.btn_med, self.btn_hard, self.btn_back, self.btn_special_toggle]: btn.draw_text_and_border(img)
            elif self.state == "PLAYING":
                self.btn_pause.draw_text_and_border(img)
            elif self.state == "PAUSED":
                for btn in [self.btn_resume, self.btn_restart, self.btn_save_quit]: btn.draw_text_and_border(img)
            elif self.state == "GAME_OVER":
                self.btn_back.draw_text_and_border(img)
            elif self.state == "RECORDS":
                self.btn_back_rec.draw_text_and_border(img)
                self.btn_switch_user.draw_text_and_border(img)
                self.btn_add_user.draw_text_and_border(img)
                if not self.is_guest:
                    self.btn_delete_user.draw_text_and_border(img)
            elif self.state == "SWITCH_USER_SELECT":
                for btn in self.user_buttons: btn.draw_text_and_border(img)
                self.btn_back_from_switch.draw_text_and_border(img)

            # --- STEP 5: DRAW CURSORS ---
            for hand_lms, c_data in all_cursors_data:
                self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                
                cv2.line(img, c_data["p1"], c_data["p2"], (255, 0, 255), 2)
                cx, cy = c_data["pos"]
                
                is_fist, fist_pos = self.detect_fist_logic(img, hand_lms)
                if is_fist:
                    cv2.circle(img, fist_pos, 50, (255, 0, 0), 4)
                    cv2.putText(img, "FIST MODE", (fist_pos[0]-60, fist_pos[1]-70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

                if c_data["is_pinching"]:
                    cv2.circle(img, (cx, cy), 15, (0, 255, 0), -1) 
                else:
                    cv2.circle(img, (cx, cy), 15, (0, 0, 255), 2)  

            cv2.imshow(self.window_name, img)
            if cv2.waitKey(1) & 0xFF == 27: break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()