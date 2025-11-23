import cv2
import mediapipe as mp
import math
import random
import time
import json
import os
import numpy as np # Required for image blending (transparency)

# ==========================================
# 1. DATA MANAGER
# Handles saving and loading player stats to a JSON file.
# ==========================================
class DataManager:
    def __init__(self, filename="game_data_v3.json"):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self):
        """Loads data from JSON. Returns an empty dict if file doesn't exist."""
        if not os.path.exists(self.filename):
            return {} 
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_data(self):
        """Writes current data to the JSON file."""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def register_user(self, username):
        """
        Creates a new user profile with empty stats for all difficulty levels.
        Structure: User -> Difficulty -> {best_score, history}
        """
        if username not in self.data:
            self.data[username] = {
                "EASY": {"best_score": 0, "history": []},
                "NORMAL": {"best_score": 0, "history": []},
                "HARD": {"best_score": 0, "history": []}
            }
            self.save_data()
            return True 
        return False 

    def add_score(self, username, score, difficulty_level):
        """Saves a score to the specific difficulty level for the user."""
        if username in self.data:
            # Ensure compatibility if the JSON structure is old
            if difficulty_level not in self.data[username]:
                self.data[username][difficulty_level] = {"best_score": 0, "history": []}
            
            user_diff = self.data[username][difficulty_level]
            user_diff["history"].append(score)
            
            # Update best score if the new score is higher
            if score > user_diff["best_score"]:
                user_diff["best_score"] = score
            self.save_data()

    def delete_user(self, username):
        """Removes a user from the database."""
        if username in self.data:
            del self.data[username]
            self.save_data()

# ==========================================
# 2. UI COMPONENTS
# Classes for rendering Buttons and the Virtual Keyboard.
# ==========================================
class Button:
    def __init__(self, text, pos, size=(200, 60), color=(200, 200, 200), text_scale=1.0):
        self.text = text
        self.x, self.y = pos
        self.w, self.h = size
        self.color = color
        self.hover_color = (0, 255, 0) # Green when hovered
        self.text_scale = text_scale

    def is_hovering(self, x, y):
        """Checks if coordinate (x, y) is inside the button's rectangle."""
        return self.x < x < self.x + self.w and self.y < y < self.y + self.h

    def draw_on_overlay(self, overlay, is_hovered=False):
        """
        Pass 1: Draws the background rectangle onto the 'overlay' image.
        This is used later for transparency (alpha blending).
        """
        color = self.hover_color if is_hovered else self.color
        cv2.rectangle(overlay, (self.x, self.y), (self.x + self.w, self.y + self.h), color, -1)
        
    def draw_text_and_border(self, img):
        """
        Pass 2: Draws the text and border directly onto the final image.
        This ensures text remains sharp and opaque (not transparent).
        """
        # Draw Border
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), (50, 50, 50), 2)
        
        # Draw Text (Centered)
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(self.text, font, self.text_scale, 2)[0]
        text_x = self.x + (self.w - text_size[0]) // 2
        text_y = self.y + (self.h + text_size[1]) // 2
        cv2.putText(img, self.text, (text_x, text_y), font, self.text_scale, (0,0,0), 2)

class VirtualKeyboard:
    """A grid of A-Z buttons for user login."""
    def __init__(self, start_x, start_y):
        self.keys = []
        self.input_text = ""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Generate A-Z grid
        for i, char in enumerate(chars):
            row = i // 7
            col = i % 7
            x = start_x + col * 70
            y = start_y + row * 70
            self.keys.append(Button(char, (x, y), (60, 60), text_scale=0.8))
            
        # Functional Buttons
        self.btn_del = Button("DEL", (start_x, start_y + 280), (130, 60))
        self.btn_enter = Button("ENTER", (start_x + 140, start_y + 280), (200, 60))

    def draw(self, img, overlay, cursor_positions):
        """Draws the keyboard background boxes onto the overlay."""
        # Input Box Background
        cv2.rectangle(overlay, (400, 100), (880, 180), (255, 255, 255), -1)
        
        # Keys Background
        buttons = self.keys + [self.btn_del, self.btn_enter]
        for btn in buttons:
            # Check if ANY active hand cursor is hovering over this key
            is_hover = any(btn.is_hovering(*pos) for pos in cursor_positions)
            btn.draw_on_overlay(overlay, is_hover)
            
    def draw_text(self, img):
        """Draws the letters and input text onto the main image."""
        # Draw Input Text
        cv2.rectangle(img, (400, 100), (880, 180), (0, 0, 0), 2)
        cv2.putText(img, self.input_text + "|", (420, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
        
        # Draw Key Labels
        buttons = self.keys + [self.btn_del, self.btn_enter]
        for btn in buttons:
            btn.draw_text_and_border(img)

    def handle_click(self, pos):
        """Handles logic when a click occurs at 'pos'."""
        for btn in self.keys:
            if btn.is_hovering(pos[0], pos[1]):
                if len(self.input_text) < 10: self.input_text += btn.text
                return None
        
        if self.btn_del.is_hovering(pos[0], pos[1]):
            self.input_text = self.input_text[:-1]
            return None
            
        if self.btn_enter.is_hovering(pos[0], pos[1]):
            if len(self.input_text) > 0: return "ENTER_PRESSED"
        return None

# ==========================================
# 3. MAIN GAME CLASS
# The core engine handling tracking, logic, and rendering.
# ==========================================
class HandGame:
    def __init__(self):
        # --- Camera Setup ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280) # Width
        self.cap.set(4, 720)  # Height
        
        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        # max_num_hands=2 allows two-player or two-hand interaction
        self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

        # --- Game System ---
        self.db = DataManager()
        self.width = 1280
        self.height = 720
        self.center = (self.width // 2, self.height // 2)
        
        self.running = True # Controls the main application loop
        self.state = "LOGIN"
        self.current_user = None
        self.current_difficulty = "NORMAL"
        
        # --- Pinch Logic Variables ---
        # Stores click state per hand ID to prevent "Machine Gun" rapid clicking
        self.hand_clicked_status = {} 
        self.pinch_threshold = 20 # Pixels distance to trigger a click

        # --- Fist Logic Variable ---
        self.hand_fist_status = {}
        self.fist_threshold = 30 # Distance between fingertips and knuckles to determine fist shape

        # --- Instantiate UI ---
        self.keyboard = VirtualKeyboard(400, 250)
        
        self.btn_start = Button("START GAME", (540, 300))
        self.btn_records = Button("RECORDS", (540, 400))
        self.btn_exit = Button("EXIT", (540, 500))
        
        self.btn_easy = Button("EASY", (300, 300), color=(150, 255, 150))
        self.btn_med = Button("NORMAL", (540, 300), color=(150, 150, 255))
        self.btn_hard = Button("HARD", (780, 300), color=(150, 150, 150))
        self.btn_back = Button("BACK", (540, 500))

        self.btn_back_rec = Button("BACK", (900, 600))
        self.btn_delete_user = Button("DELETE USER", (100, 600), size=(250, 60), color=(100, 100, 255))

        self.enemies = []
        self.score = 0
        self.difficulty_settings = {}
        self.set_difficulty("NORMAL") 

    def set_difficulty(self, level):
        """Sets game parameters (Speed, Spawn Rate) based on difficulty."""
        self.current_difficulty = level 
        if level == "EASY":
            self.difficulty_settings = {"spawn_rate": 1.5, "speed_base": 2, "speed_mult": 0.05}
        elif level == "NORMAL":
            self.difficulty_settings = {"spawn_rate": 1.0, "speed_base": 4, "speed_mult": 0.1}
        elif level == "HARD":
            self.difficulty_settings = {"spawn_rate": 0.6, "speed_base": 6, "speed_mult": 0.2}
        self.spawn_interval = self.difficulty_settings["spawn_rate"]

    def spawn_enemy(self):
        """Spawns an enemy at a random edge moving towards the center."""
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top': x, y = random.randint(0, self.width), 0
        elif side == 'bottom': x, y = random.randint(0, self.width), self.height
        elif side == 'left': x, y = 0, random.randint(0, self.height)
        else: x, y = self.width, random.randint(0, self.height)
        
        # Calculate velocity vector
        angle = math.atan2(self.center[1] - y, self.center[0] - x)
        speed = self.difficulty_settings["speed_base"] + (self.score * self.difficulty_settings["speed_mult"])
        
        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'radius': 25,
            'color': (0, 0, 255) # Red
        })

    def detect_pinch_logic(self, img, hand_lms, hand_id):
        """
        Calculates pinch distance between Thumb(4) and Index(8).
        Returns: 
            is_clicking (bool): True ONLY on the frame the pinch starts.
            cursor_data (dict): Position and geometric data for drawing later.
        """
        h, w, _ = img.shape
        thumb = hand_lms.landmark[4]
        index = hand_lms.landmark[8]
        middle = hand_lms.landmark[12]
        ring = hand_lms.landmark[16]
        little = hand_lms.landmark[20]

        

        # Convert normalized coordinates to pixel coordinates
        x4, y4 = int(thumb.x * w), int(thumb.y * h)
        x8, y8 = int(index.x * w), int(index.y * h)
        x12, y12 = int(middle.x * w), int(middle.y * h)
        x16, y16 = int(ring.x * w), int(ring.y * h)
        x20, y20 = int(little.x * w), int(little.y * h)
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2 # Midpoint

        # Distance
        length = math.hypot(x8 - x4, y8 - y4)
        m_length = math.hypot(x12 - x4, y12 - y4)
        r_length = math.hypot(x16 - x4, y16 - y4)
        l_length = math.hypot(x20 - x4, y20 - y4)

        is_pinch = False
        state_locked = self.hand_pinch_status.get(hand_id, False)

        # --- Debounce Logic ---
        if length < self.pinch_threshold:
            if not state_locked:
                is_clicking = True
                self.hand_pinch_status[hand_id] = True # Lock status
        else:
            self.hand_pinch_status[hand_id] = False # Release lock
            
        cursor_data = {
            "pos": (cx, cy),
            "p1": (x4, y4),
            "p2": (x8, y8),
            "p3": (x12, y12),
            "p4": (x16, y16),
            "p5": (x20, y20),
            "is_pinching": length < self.pinch_threshold
        }
        return is_clicking, cursor_data

    def detect_fist_logic(self, img, hand_lms, hand_id):
        """
        Calculates distance between fingertips and knuckle indeces, to figure out fist shape.
        Returns: 
            is_fist (bool): True ONLY when fist made.
            cursor_data (dict): Position and geometric data for drawing later.
        """
        h, w, _ = img.shape
        thumb = hand_lms.landmark[4]
        index = hand_lms.landmark[8]
        middle = hand_lms.landmark[12]
        ring = hand_lms.landmark[16]
        little = hand_lms.landmark[20]

        t_knuckle = hand_lms.landmark[1]
        i_knuckle = hand_lms.landmark[5]
        m_knuckle = hand_lms.landmark[9]
        r_knuckle = hand_lms.landmark[13]
        l_knuckle = hand_lms.landmark[17]

        # Convert normalized coordinates to pixel coordinates
        x1, y1 = int(t_knuckle.x * w), int(t_knuckle.y * h)
        x4, y4 = int(thumb.x * w), int(thumb.y * h)
        x5, y5 = int(i_knuckle.x * w), int(i_knuckle.y * h)
        x8, y8 = int(index.x * w), int(index.y * h)
        x9, y9 = int(m_knuckle.x * w), int(m_knuckle.y * h)
        x12, y12 = int(middle.x * w), int(middle.y * h)
        x13, y13 = int(r_knuckle.x * w), int(r_knuckle.y * h)
        x16, y16 = int(ring.x * w), int(ring.y * h)
        x17, y17 = int(l_knuckle.x * w), int(l_knuckle.y * h)
        x20, y20 = int(little.x * w), int(little.y * h)
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2 # Midpoint

        # Distance
        i_length = math.hypot(x8 - x5, y8 - y5)
        m_length = math.hypot(x12 - x9, y12 - y9)
        r_length = math.hypot(x16 - x13, y16 - y13)
        l_length = math.hypot(x20 - x17, y20 - y17)

        is_fist = False
        state_locked = self.hand_fist_status.get(hand_id, False)

        # --- Debounce Logic ---
        if (i_length < self.fist_threshold and m_length < self.fist_threshold and r_length < self.fist_threshold and l_length < self.fist_threshold):
            if not state_locked:
                is_fist = True
                self.hand_fist_status[hand_id] = True # Lock status
        else:
            self.hand_fist_status[hand_id] = False # Release lock
            
        cursor_data = {
            "pos": (cx, cy),
            "p1": (x4, y4),
            "p2": (x8, y8),
            "p3": (x12, y12),
            "p4": (x16, y16),
            "p5": (x20, y20),
            "k1": (x1, y1),
            "k2": (x5, y5),
            "k3": (x9, y9),
            "k4": (x13, y13),
            "k5": (x17, y17),
            "is_fist": (i_length < self.fist_threshold and m_length < self.fist_threshold and r_length < self.fist_threshold and l_length < self.fist_threshold)
        }
        return is_fist, cursor_data

    def run(self):
        """The Main Game Loop"""
        while self.running: 
            success, img = self.cap.read()
            if not success: break
            
            # Flip image for "Mirror" effect (Intuitive user experience)
            img = cv2.flip(img, 1)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            # --- STEP 1: LOGIC PHASE (Process Inputs) ---
            all_clicks = []       # Coordinates where a click happened this frame
            all_cursors_data = [] # Data required to draw cursors later
            cursor_positions = [] # Just (x,y) for hover detection
            
            if results.multi_hand_landmarks:
                for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                    # Detect pinch logic without drawing yet
                    clicked, cursor_data = self.detect_pinch_logic(img, hand_lms, idx)
                    
                    all_cursors_data.append((hand_lms, cursor_data))
                    cursor_positions.append(cursor_data["pos"])
                    if clicked:
                        all_clicks.append(cursor_data["pos"])

            # --- STEP 2: STATE UPDATE & OVERLAY PREPARATION ---
            # Create a copy of the image for drawing transparent UI elements
            overlay = img.copy()

            if self.state == "LOGIN":
                cv2.putText(img, "PLEASE ENTER NAME", (400, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                # Draw keyboard background on overlay
                self.keyboard.draw(img, overlay, cursor_positions) 
                
                # Logic: Check clicks on keyboard
                for click_pos in all_clicks:
                    res = self.keyboard.handle_click(click_pos)
                    if res == "ENTER_PRESSED":
                        self.current_user = self.keyboard.input_text
                        self.db.register_user(self.current_user)
                        self.state = "MENU"

            elif self.state == "MENU":
                cv2.putText(img, f"Welcome, {self.current_user}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                
                # Draw buttons on overlay
                for btn in [self.btn_start, self.btn_records, self.btn_exit]:
                    is_hover = any(btn.is_hovering(*c) for c in cursor_positions)
                    btn.draw_on_overlay(overlay, is_hover) 
                
                # Logic: Check menu clicks
                for click_pos in all_clicks:
                    if self.btn_start.is_hovering(*click_pos): self.state = "DIFFICULTY"
                    elif self.btn_records.is_hovering(*click_pos): self.state = "RECORDS"
                    elif self.btn_exit.is_hovering(*click_pos): 
                        self.running = False # Clean exit

            elif self.state == "DIFFICULTY":
                cv2.putText(img, "SELECT DIFFICULTY", (450, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)
                
                for btn in [self.btn_easy, self.btn_med, self.btn_hard, self.btn_back]:
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
                    
                    # Reset game state if starting
                    if self.state == "PLAYING":
                        self.enemies = []
                        self.score = 0
                        self.last_spawn_time = time.time()

            elif self.state == "PLAYING":
                cv2.circle(img, self.center, 30, (0, 255, 0), -1)
                cv2.putText(img, f"Score: {self.score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2)
                cv2.putText(img, f"Diff: {self.current_difficulty}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
                
                # Enemy Spawning
                if time.time() - self.last_spawn_time > self.spawn_interval:
                    self.spawn_enemy()
                    self.last_spawn_time = time.time()
                
                # Update Enemies
                for enemy in self.enemies[:]:
                    enemy['x'] += enemy['vx']
                    enemy['y'] += enemy['vy']
                    
                    # Check Attack Collision (Hand vs Enemy)
                    hit_enemy = False
                    for click_pos in all_clicks:
                        dist = math.hypot(enemy['x'] - click_pos[0], enemy['y'] - click_pos[1])
                        if dist < (enemy['radius'] + 30):
                            self.enemies.remove(enemy)
                            self.score += 1
                            hit_enemy = True
                            break 
                    
                    if hit_enemy: continue

                    # Check Game Over Collision (Enemy vs Player)
                    if math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1]) < 40:
                        self.state = "GAME_OVER"
                        self.db.add_score(self.current_user, self.score, self.current_difficulty)
                    
                    # Draw Enemy
                    cv2.circle(img, (int(enemy['x']), int(enemy['y'])), int(enemy['radius']), enemy['color'], -1)

            elif self.state == "GAME_OVER":
                # Darken the background
                cv2.rectangle(overlay, (0,0), (self.width, self.height), (0,0,0), -1)
                
                cv2.putText(img, "GAME OVER", (450, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                cv2.putText(img, f"Final Score: {self.score}", (500, 380), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                is_hover = any(self.btn_back.is_hovering(*c) for c in cursor_positions)
                self.btn_back.draw_on_overlay(overlay, is_hover)
                
                for click_pos in all_clicks:
                    if self.btn_back.is_hovering(*click_pos):
                        self.state = "MENU"

            elif self.state == "RECORDS":
                # Draw Semi-transparent background panel
                cv2.rectangle(overlay, (100, 100), (1180, 650), (240, 240, 240), -1)
                
                cv2.putText(img, "PLAYER RECORDS", (480, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (50, 50, 50), 3)
                
                user_data = self.db.data.get(self.current_user, {})
                
                # Display stats
                y_offset = 220
                cv2.putText(img, f"User: {self.current_user}", (150, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                y_offset += 50
                
                for diff in ["EASY", "NORMAL", "HARD"]:
                    d_data = user_data.get(diff, {"best_score": 0, "history": []})
                    best = d_data["best_score"]
                    count = len(d_data["history"])
                    text = f"{diff} - Best: {best} | Games: {count}"
                    cv2.putText(img, text, (150, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,100,0), 2)
                    y_offset += 40

                self.btn_back_rec.draw_on_overlay(overlay, any(self.btn_back_rec.is_hovering(*c) for c in cursor_positions))
                self.btn_delete_user.draw_on_overlay(overlay, any(self.btn_delete_user.is_hovering(*c) for c in cursor_positions))
                
                for click_pos in all_clicks:
                    if self.btn_back_rec.is_hovering(*click_pos):
                        self.state = "MENU"
                    elif self.btn_delete_user.is_hovering(*click_pos):
                        self.db.delete_user(self.current_user)
                        self.keyboard.input_text = ""
                        self.state = "LOGIN"

            # --- STEP 3: COMPOSITING (Transparency) ---
            # Blend the 'overlay' onto 'img'. alpha=0.3 means 30% overlay opacity (70% transparency).
            alpha = 0.3 
            if self.state == "GAME_OVER": alpha = 0.6 # Darker background for game over
            
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

            # --- STEP 4: DRAW TEXT (Top Layer) ---
            # Text is drawn AFTER blending so it remains sharp and opaque.
            if self.state == "LOGIN": self.keyboard.draw_text(img)
            elif self.state == "MENU": 
                for btn in [self.btn_start, self.btn_records, self.btn_exit]: btn.draw_text_and_border(img)
            elif self.state == "DIFFICULTY":
                for btn in [self.btn_easy, self.btn_med, self.btn_hard, self.btn_back]: btn.draw_text_and_border(img)
            elif self.state == "GAME_OVER":
                self.btn_back.draw_text_and_border(img)
            elif self.state == "RECORDS":
                self.btn_back_rec.draw_text_and_border(img)
                self.btn_delete_user.draw_text_and_border(img)

            # --- STEP 5: DRAW CURSORS (Highest Z-Order) ---
            # Drawn last to ensure they appear on top of menus and text.
            for hand_lms, c_data in all_cursors_data:
                # Draw skeleton
                self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                
                # Draw Line connecting Thumb and Index
                cv2.line(img, c_data["p1"], c_data["p2"], (255, 0, 255), 2)
                
                # Draw Cursor Circle (Green=Clicking, Red=Hovering)
                cx, cy = c_data["pos"]
                if c_data["is_pinching"]:
                    cv2.circle(img, (cx, cy), 15, (0, 255, 0), -1) 
                else:
                    cv2.circle(img, (cx, cy), 15, (0, 0, 255), 2)  

            cv2.imshow("Hand Game Ultimate V3", img)
            if cv2.waitKey(1) & 0xFF == 27: break # ESC key to force close

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()