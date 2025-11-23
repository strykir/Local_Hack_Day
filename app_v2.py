import cv2
import mediapipe as mp
import math
import random
import time
from src.DataManager import DataManager
from src.Components import Button, VirtualKeyboard

# ==========================================
# 3. MAIN GAME CLASS
# ==========================================
class HandGame:
    def __init__(self):
        # --- Camera Setup ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)
        
        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        # Enable max 2 hands for dual-hand interaction
        self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

        # --- Data & System ---
        self.db = DataManager()
        self.width = 1280
        self.height = 720
        self.center = (self.width // 2, self.height // 2)
        
        # --- Game State Variables ---
        self.running = True
        self.state = "LOGIN" 
        self.current_user = None
        self.is_guest = False 
        self.current_difficulty = "NORMAL"
        
        # --- Gesture Logic Variables ---
        self.hand_clicked_status = {} # Dictionary for Pinch debounce
        self.pinch_threshold = 40
        
        # Special Mode Toggle
        self.enable_special_enemies = False 

        # --- UI ELEMENTS ---
        self.keyboard = VirtualKeyboard(400, 250)
        
        # 1. Login/Add User Buttons
        self.btn_skip = Button("SKIP (GUEST)", (950, 600), size=(280, 60), color=(150, 200, 255))
        self.btn_back_to_record_kb = Button("BACK", (50, 600), size=(200, 60), color=(255, 100, 100))
        
        # 2. Confirm Screen Buttons
        self.btn_confirm_yes = Button("CONFIRM", (380, 400), color=(150, 255, 150))
        self.btn_confirm_no = Button("GO BACK", (700, 400), color=(255, 150, 150))

        # 3. Delete Confirm Screen Buttons
        self.btn_delete_yes = Button("YES, DELETE", (380, 400), color=(255, 100, 100)) 
        self.btn_delete_no = Button("NO, GO BACK", (700, 400), color=(150, 255, 150)) 

        # 4. Menu Buttons
        self.btn_start = Button("START GAME", (540, 300))
        self.btn_records = Button("RECORDS", (540, 400))
        self.btn_exit = Button("EXIT", (540, 500))
        
        # 5. Difficulty & Special Toggle Buttons
        self.btn_easy = Button("EASY", (300, 300), color=(150, 255, 150))
        self.btn_med = Button("NORMAL", (540, 300), color=(150, 150, 255))
        self.btn_hard = Button("HARD", (780, 300), color=(150, 150, 150))
        self.btn_back = Button("BACK", (540, 500))
        self.btn_special_toggle = Button("SPECIAL: OFF", (540, 400), size=(250, 60), color=(200, 200, 200))

        # 6. Records Screen Buttons
        self.btn_back_rec = Button("BACK", (900, 600))
        self.btn_delete_user = Button("DELETE USER", (100, 600), size=(250, 60), color=(100, 100, 255))
        self.btn_switch_user = Button("SWITCH USER", (500, 600), size=(250, 60), color=(255, 255, 150))
        self.btn_add_user = Button("ADD USER", (500, 520), size=(250, 60), color=(200, 255, 200))

        # 7. Switch User Select Screen
        self.user_buttons = []
        self.btn_back_from_switch = Button("BACK", (540, 620))

        # 8. Pause Menu Buttons
        self.btn_pause = Button("II", (1150, 30), size=(80, 60), color=(255, 255, 200)) 
        self.btn_resume = Button("RESUME", (540, 250), color=(150, 255, 150))
        self.btn_restart = Button("RESTART", (540, 350), color=(255, 255, 150))
        self.btn_save_quit = Button("SAVE & QUIT", (540, 450), color=(255, 150, 150))

        self.enemies = []
        self.score = 0
        self.difficulty_settings = {}
        self.set_difficulty("NORMAL") 

    def refresh_user_buttons(self):
        """Generates the grid of buttons for the user list."""
        users = self.db.get_user_list()
        self.user_buttons = []
        start_x, start_y = 100, 150
        col_width = 320
        row_height = 80
        for i, u_name in enumerate(users):
            row = i // 3
            col = i % 3
            x = start_x + col * (col_width + 50)
            y = start_y + row * (row_height + 20)
            # Limit to first 15 users for this simple grid
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
        """Spawns an enemy at a random edge."""
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top': x, y = random.randint(0, self.width), 0
        elif side == 'bottom': x, y = random.randint(0, self.width), self.height
        elif side == 'left': x, y = 0, random.randint(0, self.height)
        else: x, y = self.width, random.randint(0, self.height)
        
        angle = math.atan2(self.center[1] - y, self.center[0] - x)
        speed = self.difficulty_settings["speed_base"] + (self.score * self.difficulty_settings["speed_mult"])
        
        enemy_type = 'circle'
        enemy_color = (0, 0, 255) # Red for Circle

        # Special Enemy Logic: Only in HARD mode + Toggle enabled + 30% chance
        if self.enable_special_enemies:
            if random.random() < 0.3:
                enemy_type = 'square'
                enemy_color = (255, 0, 0) # Blue for Square

        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'radius': 30,
            'color': enemy_color,
            'type': enemy_type
        })

    def detect_fist_logic(self, img, hand_lms):
        """
        Determines if the hand is in a Fist state.
        Checks the distance of 4 finger tips (Index, Middle, Ring, Pinky) to the Wrist (0).
        """
        h, w, _ = img.shape
        # wrist = hand_lms.landmark[0]
        finger_tips = [8, 12, 16, 20]
        
        total_dist = 0
        for tip_id in finger_tips:
            tip = hand_lms.landmark[tip_id]
            hand_point = hand_lms.landmark[tip_id - 3]
            # dist = math.hypot(tip.x * w - wrist.x * w, tip.y * h - wrist.y * h)
            dist = math.hypot(tip.x * w - hand_point.x * w, tip.y * h - hand_point.y * h)
            total_dist += dist

        # Use Middle Finger MCP (9) as the center point of the fist impact
        middle_mcp = hand_lms.landmark[9]
        cx, cy = int(middle_mcp.x * w), int(middle_mcp.y * h)

        # Threshold to detect a closed fist
        is_fist = total_dist < 400 

        return is_fist, (cx, cy)

    def detect_pinch_logic(self, img, hand_lms, hand_id):
        """Detects pinch gesture (Index + Thumb)."""
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

            # --- STEP 1: LOGIC PHASE ---
            all_clicks = []      
            all_cursors_data = [] 
            cursor_positions = [] 
            all_fists = [] 
            
            if results.multi_hand_landmarks:
                for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                    # 1. Detect Pinch
                    clicked, cursor_data = self.detect_pinch_logic(img, hand_lms, idx)
                    all_cursors_data.append((hand_lms, cursor_data))
                    cursor_positions.append(cursor_data["pos"])
                    if clicked:
                        all_clicks.append(cursor_data["pos"])
                    
                    # 2. Detect Fist
                    is_fist, fist_pos = self.detect_fist_logic(img, hand_lms)
                    if is_fist:
                        all_fists.append(fist_pos)

            # --- STEP 2: STATE UPDATE & OVERLAY ---
            overlay = img.copy()

            # --- STATE: LOGIN ---
            if self.state == "LOGIN":
                cv2.putText(img, "PLEASE ENTER NAME", (400, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
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

            # --- STATE: ADD USER INPUT ---
            elif self.state == "ADD_USER_INPUT":
                cv2.putText(img, "CREATE NEW USER", (400, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.keyboard.draw(img, overlay, cursor_positions)
                self.btn_back_to_record_kb.draw_on_overlay(overlay, any(self.btn_back_to_record_kb.is_hovering(*c) for c in cursor_positions))

                for click_pos in all_clicks:
                    res = self.keyboard.handle_click(click_pos)
                    if res == "ENTER_PRESSED":
                        self.next_state_after_confirm = "ADD_SUCCESS"
                        self.state = "CONFIRM_ACTION"
                    if self.btn_back_to_record_kb.is_hovering(*click_pos):
                        self.state = "RECORDS"

            # --- STATE: CONFIRM ACTION (Login / Add) ---
            elif self.state == "CONFIRM_ACTION":
                cv2.rectangle(overlay, (300, 200), (980, 500), (255, 255, 255), -1)
                
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

            # --- STATE: CONFIRM DELETE ---
            elif self.state == "CONFIRM_DELETE":
                cv2.rectangle(overlay, (200, 150), (1080, 550), (200, 200, 255), -1)
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

            # --- STATE: MENU ---
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

            # --- STATE: DIFFICULTY SELECT ---
            elif self.state == "DIFFICULTY":
                cv2.putText(img, "SELECT DIFFICULTY", (450, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)
                
                # Render Special Enemy Toggle
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

            # --- STATE: PLAYING ---
            elif self.state == "PLAYING":
                cv2.circle(img, self.center, 30, (0, 255, 0), -1)
                cv2.putText(img, f"Score: {self.score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2)
                cv2.putText(img, f"Diff: {self.current_difficulty}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
                if self.is_guest:
                     cv2.putText(img, "GUEST MODE (NO SAVE)", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

                # Draw Pause Button
                is_hover_pause = any(self.btn_pause.is_hovering(*c) for c in cursor_positions)
                self.btn_pause.draw_on_overlay(overlay, is_hover_pause)

                # Check Pause Click
                for click_pos in all_clicks:
                    if self.btn_pause.is_hovering(*click_pos):
                        self.state = "PAUSED"

                # Spawn Enemy Logic
                if time.time() - self.last_spawn_time > self.spawn_interval:
                    self.spawn_enemy()
                    self.last_spawn_time = time.time()
                
                # --- Core Collision & Update Loop ---
                for enemy in self.enemies[:]:
                    enemy['x'] += enemy['vx']
                    enemy['y'] += enemy['vy']
                    
                    hit_enemy = False
                    
                    # Case 1: Circle Enemy (Red) -> Only responds to Pinch
                    if enemy['type'] == 'circle':
                        for click_pos in all_clicks:
                            if math.hypot(enemy['x'] - click_pos[0], enemy['y'] - click_pos[1]) < (enemy['radius'] + 30):
                                self.enemies.remove(enemy)
                                self.score += 1
                                hit_enemy = True
                                break 
                    
                    # Case 2: Square Enemy (Blue) -> Only responds to Fist
                    elif enemy['type'] == 'square':
                        for fist_pos in all_fists:
                             # Fist hit radius is slightly larger (+40)
                             if math.hypot(enemy['x'] - fist_pos[0], enemy['y'] - fist_pos[1]) < (enemy['radius'] + 40): 
                                self.enemies.remove(enemy)
                                self.score += 2
                                hit_enemy = True
                                break

                    if hit_enemy: continue

                    # Game Over Condition (Enemy hits player)
                    if math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1]) < 40:
                        self.state = "GAME_OVER"
                        if not self.is_guest:
                            self.db.add_score(self.current_user, self.score, self.current_difficulty)
                    
                    # Draw Enemies based on Type
                    if enemy['type'] == 'circle':
                        cv2.circle(img, (int(enemy['x']), int(enemy['y'])), int(enemy['radius']), enemy['color'], -1)
                    else: # Square
                        r = int(enemy['radius'])
                        top_left = (int(enemy['x']) - r, int(enemy['y']) - r)
                        bottom_right = (int(enemy['x']) + r, int(enemy['y']) + r)
                        cv2.rectangle(img, top_left, bottom_right, enemy['color'], -1)
                        cv2.rectangle(img, top_left, bottom_right, (255, 255, 255), 2) # White Border

            # --- STATE: PAUSED ---
            elif self.state == "PAUSED":
                cv2.rectangle(overlay, (400, 100), (880, 600), (200, 200, 200), -1)
                cv2.putText(img, "PAUSED", (560, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
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

            # --- STATE: GAME OVER ---
            elif self.state == "GAME_OVER":
                cv2.rectangle(overlay, (0,0), (self.width, self.height), (0,0,0), -1)
                cv2.putText(img, "GAME OVER", (450, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                cv2.putText(img, f"Final Score: {self.score}", (500, 380), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                self.btn_back.draw_on_overlay(overlay, any(self.btn_back.is_hovering(*c) for c in cursor_positions))
                for click_pos in all_clicks:
                    if self.btn_back.is_hovering(*click_pos): self.state = "MENU"

            # --- STATE: RECORDS ---
            elif self.state == "RECORDS":
                cv2.rectangle(overlay, (100, 100), (1180, 680), (240, 240, 240), -1)
                cv2.putText(img, "PLAYER RECORDS", (480, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (50, 50, 50), 3)
                if self.is_guest:
                    cv2.putText(img, "Guest User - No Records Found", (350, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (100,100,100), 2)
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

            # --- STATE: SWITCH USER SELECT ---
            elif self.state == "SWITCH_USER_SELECT":
                cv2.rectangle(overlay, (50, 50), (1230, 670), (240, 240, 240), -1)
                cv2.putText(img, "SELECT USER", (520, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
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
            elif self.state == "PAUSED": alpha = 0.4 # Darker background for pause
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

            # --- STEP 4: DRAW TEXT LAYERS ---
            if self.state == "LOGIN": 
                self.keyboard.draw_text(img)
                self.btn_skip.draw_text_and_border(img)
            elif self.state == "ADD_USER_INPUT":
                self.keyboard.draw_text(img)
                self.btn_back_to_record_kb.draw_text_and_border(img)
            elif self.state == "CONFIRM_ACTION":
                cv2.putText(img, f"Confirm name: '{self.keyboard.input_text}'?", (420, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.btn_confirm_yes.draw_text_and_border(img)
                self.btn_confirm_no.draw_text_and_border(img)
            elif self.state == "CONFIRM_DELETE":
                cv2.putText(img, "ARE YOU SURE?", (500, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
                cv2.putText(img, f"Delete User: {self.current_user}", (450, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
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
                
                # Draw Pinch Line
                cv2.line(img, c_data["p1"], c_data["p2"], (255, 0, 255), 2)
                cx, cy = c_data["pos"]
                
                # Draw Fist Hint (Only if fist is detected)
                is_fist, fist_pos = self.detect_fist_logic(img, hand_lms)
                if is_fist:
                    # Draw a distinctive blue circle for "Heavy Attack Mode"
                    cv2.circle(img, fist_pos, 50, (255, 0, 0), 4)
                    cv2.putText(img, "FIST MODE", (fist_pos[0]-60, fist_pos[1]-70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

                if c_data["is_pinching"]:
                    cv2.circle(img, (cx, cy), 15, (0, 255, 0), -1) 
                else:
                    cv2.circle(img, (cx, cy), 15, (0, 0, 255), 2)  

            cv2.imshow("Hand Game Ultimate V8", img)
            if cv2.waitKey(1) & 0xFF == 27: break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()