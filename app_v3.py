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
        # --- Camera Setup ---
        self.cap = cv2.VideoCapture(0)
        
        # [MODIFIED] Adaptive Resolution
        # We attempt to set 1280x720, but we read back what the camera actually supports.
        self.cap.set(3, 1280)
        self.cap.set(4, 720)
        self.width = int(self.cap.get(3))
        self.height = int(self.cap.get(4))
        self.center = (self.width // 2, self.height // 2)
        
        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

        # --- Data & System ---
        self.db = DataManager()
        
        # --- Game State Variables ---
        self.running = True
        self.state = "LOGIN" 
        self.current_user = None
        self.is_guest = False 
        self.current_difficulty = "NORMAL"
        
        # --- Gesture Logic Variables ---
        self.hand_clicked_status = {} 
        self.pinch_threshold = 40
        self.enable_special_enemies = False 

        # ===============================================================
        # [NEW] ICON LOADING SYSTEM
        # We load images into lists. If list is empty, we use shapes.
        # ===============================================================
        self.icons_pinch = self.load_images_from_folder("src/icons/pinch")
        self.icons_fist = self.load_images_from_folder("src/icons/fist")

        # --- UI ELEMENTS (Dynamic Positioning) ---
        # [MODIFIED] All positions are now calculated relative to self.width/self.height
        
        self.keyboard = VirtualKeyboard(int(self.width * 0.3), int(self.height * 0.35))
        
        # Common center X for menus
        cx_menu = (self.width - 200) // 2 
        
        # 1. Login/Add User Buttons
        # Position: Bottom Right
        self.btn_skip = Button("SKIP (GUEST)", (self.width - 300, self.height - 100), size=(280, 60), color=(150, 200, 255))
        self.btn_back_to_record_kb = Button("BACK", (50, self.height - 100), size=(200, 60), color=(255, 100, 100))
        
        # 2. Confirm Screen Buttons
        self.btn_confirm_yes = Button("CONFIRM", (cx_menu - 150, 400), color=(150, 255, 150))
        self.btn_confirm_no = Button("GO BACK", (cx_menu + 150, 400), color=(255, 150, 150))

        # 3. Delete Confirm Screen Buttons
        self.btn_delete_yes = Button("YES, DELETE", (cx_menu - 150, 400), color=(255, 100, 100)) 
        self.btn_delete_no = Button("NO, GO BACK", (cx_menu + 150, 400), color=(150, 255, 150)) 

        # 4. Menu Buttons (Centered)
        self.btn_start = Button("START GAME", (cx_menu, 300))
        self.btn_records = Button("RECORDS", (cx_menu, 400))
        self.btn_exit = Button("EXIT", (cx_menu, 500))
        
        # 5. Difficulty & Special Toggle Buttons
        # Calculated to spread evenly
        step_x = self.width // 5
        self.btn_easy = Button("EASY", (step_x - 100, 300), color=(150, 255, 150))
        self.btn_med = Button("NORMAL", (step_x * 2 - 100, 300), color=(150, 150, 255))
        self.btn_hard = Button("HARD", (step_x * 3 - 100, 300), color=(150, 150, 150))
        
        self.btn_back = Button("BACK", (cx_menu, 500))
        self.btn_special_toggle = Button("SPECIAL: OFF", (cx_menu, 400), size=(250, 60), color=(200, 200, 200))

        # 6. Records Screen Buttons
        self.btn_back_rec = Button("BACK", (self.width - 250, self.height - 100))
        self.btn_delete_user = Button("DELETE USER", (50, self.height - 100), size=(250, 60), color=(100, 100, 255))
        self.btn_switch_user = Button("SWITCH USER", (cx_menu, self.height - 100), size=(250, 60), color=(255, 255, 150))
        self.btn_add_user = Button("ADD USER", (cx_menu, self.height - 180), size=(250, 60), color=(200, 255, 200))

        # 7. Switch User Select Screen
        self.user_buttons = []
        self.btn_back_from_switch = Button("BACK", (cx_menu, self.height - 100))

        # 8. Pause Menu Buttons
        # [MODIFIED] Pause button anchored to Top-Right corner
        self.btn_pause = Button("II", (self.width - 100, 30), size=(80, 60), color=(255, 255, 200)) 
        self.btn_resume = Button("RESUME", (cx_menu, 250), color=(150, 255, 150))
        self.btn_restart = Button("RESTART", (cx_menu, 350), color=(255, 255, 150))
        self.btn_save_quit = Button("SAVE & QUIT", (cx_menu, 450), color=(255, 150, 150))

        self.enemies = []
        self.score = 0
        self.difficulty_settings = {}
        self.set_difficulty("NORMAL") 

    # [NEW] Function to load images and resize them
    def load_images_from_folder(self, folder):
        images = []
        if not os.path.exists(folder):
            return []
        for filename in os.listdir(folder):
            img = cv2.imread(os.path.join(folder, filename), cv2.IMREAD_UNCHANGED) # Load with Alpha
            if img is not None:
                images.append(img)
        return images

    def refresh_user_buttons(self):
        """Generates the grid of buttons for the user list."""
        users = self.db.get_user_list()
        self.user_buttons = []
        start_x, start_y = int(self.width * 0.1), 150
        col_width = 320
        row_height = 80
        
        # [MODIFIED] Logic to wrap buttons if screen is small
        cols_per_row = max(1, (self.width - 100) // (col_width + 20))
        
        for i, u_name in enumerate(users):
            row = i // cols_per_row
            col = i % cols_per_row
            x = start_x + col * (col_width + 20)
            y = start_y + row * (row_height + 20)
            
            if i < 15:
                self.user_buttons.append(Button(u_name, (x, y), size=(col_width, row_height)))

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
        
        # Default settings
        enemy_type = 'circle'
        enemy_color = (0, 0, 255)
        icon_img = None

        # Determine Type
        is_special = False
        if self.current_difficulty == "HARD" and self.enable_special_enemies:
            if random.random() < 0.3:
                is_special = True
                enemy_type = 'square'
                enemy_color = (255, 0, 0)

        # [NEW] Assign Random Icon from loaded lists
        if is_special:
            if self.icons_fist:
                icon_img = random.choice(self.icons_fist)
        else:
            if self.icons_pinch:
                icon_img = random.choice(self.icons_pinch)

        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'radius': 35, # Increased radius slightly for icons
            'color': enemy_color,
            'type': enemy_type,
            'icon': icon_img # Store the image in the enemy object
        })

    # [NEW] Helper to draw transparent PNG over background
    def draw_enemy_icon(self, bg_img, icon, x, y, size):
        # Resize icon to fit diameter (size * 2)
        diameter = size * 2
        icon_resized = cv2.resize(icon, (diameter, diameter))
        
        # Calculate bounds
        h, w, _ = icon_resized.shape # Icon dimensions
        
        y1, y2 = y - h // 2, y + h // 2
        x1, x2 = x - w // 2, x + w // 2

        # Check boundaries (Clipping) to prevent crashes at screen edges
        if y1 < 0 or y2 > bg_img.shape[0] or x1 < 0 or x2 > bg_img.shape[1]:
            return # Skip drawing if partially off-screen (or implement complex clipping)

        # Alpha Blending
        alpha_s = icon_resized[:, :, 3] / 255.0
        alpha_l = 1.0 - alpha_s

        for c in range(0, 3):
            bg_img[y1:y2, x1:x2, c] = (alpha_s * icon_resized[:, :, c] +
                                       alpha_l * bg_img[y1:y2, x1:x2, c])

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
        is_fist = total_dist < 400 
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
                cv2.putText(img, "PLEASE ENTER NAME", (int(self.width*0.3), 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
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
                cv2.putText(img, "CREATE NEW USER", (int(self.width*0.3), 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
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
                # Dynamic Box
                box_x1, box_x2 = int(self.width * 0.25), int(self.width * 0.75)
                cv2.rectangle(overlay, (box_x1, 200), (box_x2, 500), (255, 255, 255), -1)
                
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
                box_x1, box_x2 = int(self.width * 0.15), int(self.width * 0.85)
                cv2.rectangle(overlay, (box_x1, 150), (box_x2, 550), (200, 200, 255), -1)
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
                cv2.putText(img, f"Welcome, {display_name}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                for btn in [self.btn_start, self.btn_records, self.btn_exit]:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover) 
                for click_pos in all_clicks:
                    if self.btn_start.is_hovering(*click_pos): self.state = "DIFFICULTY"
                    elif self.btn_records.is_hovering(*click_pos): self.state = "RECORDS"
                    elif self.btn_exit.is_hovering(*click_pos): self.running = False

            elif self.state == "DIFFICULTY":
                cv2.putText(img, "SELECT DIFFICULTY", (int(self.width * 0.35), 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)
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
                    elif self.btn_med.is_hovering(*click_pos):
                        self.set_difficulty("NORMAL")
                        self.state = "PLAYING"
                    elif self.btn_hard.is_hovering(*click_pos):
                        self.set_difficulty("HARD")
                        self.state = "PLAYING"
                    elif self.btn_back.is_hovering(*click_pos):
                        self.state = "MENU"
                    elif self.btn_special_toggle.is_hovering(*click_pos):
                        self.enable_special_enemies = not self.enable_special_enemies
                    
                    if self.state == "PLAYING":
                        self.enemies = []
                        self.score = 0
                        self.last_spawn_time = time.time()

            elif self.state == "PLAYING":
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
                    
                    if enemy['type'] == 'circle':
                        for click_pos in all_clicks:
                            if math.hypot(enemy['x'] - click_pos[0], enemy['y'] - click_pos[1]) < (enemy['radius'] + 30):
                                self.enemies.remove(enemy)
                                self.score += 1
                                hit_enemy = True
                                break 
                    
                    elif enemy['type'] == 'square':
                        for fist_pos in all_fists:
                             if math.hypot(enemy['x'] - fist_pos[0], enemy['y'] - fist_pos[1]) < (enemy['radius'] + 40): 
                                self.enemies.remove(enemy)
                                self.score += 2
                                hit_enemy = True
                                break

                    if hit_enemy: continue

                    if math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1]) < 40:
                        self.state = "GAME_OVER"
                        if not self.is_guest:
                            self.db.add_score(self.current_user, self.score, self.current_difficulty)
                    
                    # [MODIFIED] Draw Enemy: Check if icon exists
                    draw_x, draw_y = int(enemy['x']), int(enemy['y'])
                    
                    if enemy.get('icon') is not None:
                        # Use the custom image
                        self.draw_enemy_icon(img, enemy['icon'], draw_x, draw_y, enemy['radius'])
                    else:
                        # Fallback to shapes
                        if enemy['type'] == 'circle':
                            cv2.circle(img, (draw_x, draw_y), int(enemy['radius']), enemy['color'], -1)
                        else:
                            r = int(enemy['radius'])
                            cv2.rectangle(img, (draw_x-r, draw_y-r), (draw_x+r, draw_y+r), enemy['color'], -1)
                            cv2.rectangle(img, (draw_x-r, draw_y-r), (draw_x+r, draw_y+r), (255, 255, 255), 2)

            elif self.state == "PAUSED":
                # [MODIFIED] Dynamic Pause Menu Box
                bx1, bx2 = int(self.width*0.3), int(self.width*0.7)
                cv2.rectangle(overlay, (bx1, 100), (bx2, 600), (200, 200, 200), -1)
                cv2.putText(img, "PAUSED", (bx1 + 150, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
                
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
                    elif self.btn_save_quit.is_hovering(*click_pos):
                        if not self.is_guest: self.db.add_score(self.current_user, self.score, self.current_difficulty)
                        self.state = "MENU"

            elif self.state == "GAME_OVER":
                cv2.rectangle(overlay, (0,0), (self.width, self.height), (0,0,0), -1)
                cv2.putText(img, "GAME OVER", (int(self.width*0.35), 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                cv2.putText(img, f"Final Score: {self.score}", (int(self.width*0.4), 380), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                self.btn_back.draw_on_overlay(overlay, any(self.btn_back.is_hovering(*c) for c in cursor_positions))
                for click_pos in all_clicks:
                    if self.btn_back.is_hovering(*click_pos): self.state = "MENU"

            elif self.state == "RECORDS":
                cv2.rectangle(overlay, (100, 100), (self.width - 100, self.height - 50), (240, 240, 240), -1)
                cv2.putText(img, "PLAYER RECORDS", (int(self.width*0.35), 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (50, 50, 50), 3)
                if self.is_guest:
                    cv2.putText(img, "Guest User - No Records", (350, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (100,100,100), 2)
                    buttons_to_draw = [self.btn_back_rec, self.btn_switch_user, self.btn_add_user]
                else:
                    user_data = self.db.data.get(self.current_user, {})
                    y_offset = 220
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
                cv2.putText(img, f"Confirm name: '{self.keyboard.input_text}'?", (int(self.width*0.3), 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.btn_confirm_yes.draw_text_and_border(img)
                self.btn_confirm_no.draw_text_and_border(img)
            elif self.state == "CONFIRM_DELETE":
                cv2.putText(img, "ARE YOU SURE?", (int(self.width*0.35), 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
                cv2.putText(img, f"Delete User: {self.current_user}", (int(self.width*0.35), 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.btn_delete_yes.draw_text_and_border(img)
                self.btn_delete_no.draw_text_and_border(img)
            elif self.state == "MENU": 
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

            cv2.imshow("Hand Game Ultimate V9", img)
            if cv2.waitKey(1) & 0xFF == 27: break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()