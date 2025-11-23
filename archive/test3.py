import cv2
import mediapipe as mp
import math
import random
import time
import json
import os

# --- 1. Data Manager (Handles JSON Storage) ---
class DataManager:
    def __init__(self, filename="game_data.json"):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self):
        if not os.path.exists(self.filename):
            return {} # Return empty dict if file doesn't exist
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def register_user(self, username):
        if username not in self.data:
            self.data[username] = {"best_score": 0, "history": []}
            self.save_data()
            return True # New user created
        return False # User exists

    def add_score(self, username, score):
        if username in self.data:
            user = self.data[username]
            user["history"].append(score)
            if score > user["best_score"]:
                user["best_score"] = score
            self.save_data()

    def delete_user(self, username):
        if username in self.data:
            del self.data[username]
            self.save_data()

# --- 2. UI Components ---
class Button:
    def __init__(self, text, pos, size=(200, 60), color=(200, 200, 200), text_scale=1.0):
        self.text = text
        self.x, self.y = pos
        self.w, self.h = size
        self.color = color
        self.hover_color = (0, 255, 0)
        self.text_scale = text_scale

    def is_hovering(self, x, y):
        return self.x < x < self.x + self.w and self.y < y < self.y + self.h

    def draw(self, img, is_hovered=False):
        color = self.hover_color if is_hovered else self.color
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), color, -1) # inside
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), (50, 50, 50), 2) # boundary
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(self.text, font, self.text_scale, 2)[0]
        text_x = self.x + (self.w - text_size[0]) // 2
        text_y = self.y + (self.h + text_size[1]) // 2
        cv2.putText(img, self.text, (text_x, text_y), font, self.text_scale, (0,0,0), 2)

class VirtualKeyboard:
    """A grid of buttons for typing username."""
    def __init__(self, start_x, start_y):
        self.keys = []
        self.input_text = ""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        # Create A-Z keys
        for i, char in enumerate(chars):
            row = i // 7
            col = i % 7
            x = start_x + col * 70
            y = start_y + row * 70
            self.keys.append(Button(char, (x, y), (60, 60), text_scale=0.8))
        
        # Functional Keys
        self.btn_del = Button("DEL", (start_x, start_y + 280), (130, 60))
        self.btn_enter = Button("ENTER", (start_x + 140, start_y + 280), (200, 60))

    def draw(self, img, cursor_pos):
        # Draw Input Box
        cv2.rectangle(img, (400, 100), (880, 180), (255, 255, 255), -1)
        cv2.putText(img, self.input_text + "|", (420, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
        
        # Draw Keys
        buttons = self.keys + [self.btn_del, self.btn_enter]
        clicked_key = None
        
        for btn in buttons:
            is_hover = False
            if cursor_pos:
                is_hover = btn.is_hovering(cursor_pos[0], cursor_pos[1])
            btn.draw(img, is_hover)

    def handle_click(self, pos):
        """Returns 'ENTER_PRESSED' if enter is clicked, else updates text."""
        # Check A-Z
        for btn in self.keys:
            if btn.is_hovering(pos[0], pos[1]):
                if len(self.input_text) < 10:
                    self.input_text += btn.text
                return None
        
        # Check DEL
        if self.btn_del.is_hovering(pos[0], pos[1]):
            self.input_text = self.input_text[:-1]
            return None
            
        # Check ENTER
        if self.btn_enter.is_hovering(pos[0], pos[1]):
            if len(self.input_text) > 0:
                return "ENTER_PRESSED"
        
        return None

# --- 3. Main Game Class ---
class HandGame:
    def __init__(self):
        # Setup Camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)

        # Setup MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

        # System Logic
        self.db = DataManager()
        self.width = 1280
        self.height = 720
        self.center = (self.width // 2, self.height // 2)
        
        # State Machine
        # States: LOGIN, MENU, DIFFICULTY, PLAYING, RECORDS, GAME_OVER
        self.state = "LOGIN"
        self.current_user = None
        
        # Pinch Control
        self.hand_clicked_status = False 
        self.pinch_threshold = 40

        # UI Elements
        self.keyboard = VirtualKeyboard(400, 250)
        
        # Menu Buttons
        self.btn_start = Button("START GAME", (540, 300))
        self.btn_records = Button("RECORDS", (540, 400))
        self.btn_exit = Button("EXIT", (540, 500))
        
        # Difficulty Buttons
        self.btn_easy = Button("EASY", (300, 300), color=(150, 255, 150))
        self.btn_med = Button("NORMAL", (540, 300), color=(150, 150, 255))
        self.btn_hard = Button("HARD", (780, 300), color=(150, 150, 150))
        self.btn_back = Button("BACK", (540, 500))

        # Records Buttons
        self.btn_back_rec = Button("BACK", (900, 600))
        self.btn_delete_user = Button("DELETE USER", (100, 600), size=(250, 60), color=(100, 100, 255))

        # Game Logic Variables
        self.enemies = []
        self.score = 0
        self.difficulty_settings = {}

    def set_difficulty(self, level):
        """Configure game parameters based on level."""
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
        
        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'radius': 25,
            'color': (0, 0, 255)
        })

    def detect_pinch(self, img, hand_lms):
        """Returns (is_clicked, (x, y)) with debounce."""
        h, w, _ = img.shape
        thumb = hand_lms.landmark[4]
        index = hand_lms.landmark[8]
        middle = hand_lms.landmark[12]
        ring = hand_lms.landmark[16]
        little = hand_lms.landmark[20]

        x4, y4 = int(thumb.x * w), int(thumb.y * h)
        x8, y8 = int(index.x * w), int(index.y * h)
        x12, y12 = int(middle.x * w), int(middle.y * h)
        x16, y16 = int(ring.x * w), int(ring.y * h)
        x20, y20 = int(little.x * w), int(little.y * h)
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2
        length = math.hypot(x8 - x4, y8 - y4)

        cv2.line(img, (x4, y4), (x8, y8), (255, 0, 255), 2)
        
        clicked = False
        if length < self.pinch_threshold:
            cv2.circle(img, (cx, cy), 15, (0, 255, 0), -1) # Green = Pinch
            if not self.hand_clicked_status:
                clicked = True
                self.hand_clicked_status = True
        else:
            cv2.circle(img, (cx, cy), 15, (0, 0, 255), 2) # Red = Open
            self.hand_clicked_status = False
            
        return clicked, (cx, cy)

    def run(self):
        while True:
            success, img = self.cap.read()
            if not success: break
            img = cv2.flip(img, 1)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            # Cursor Logic
            cursor_pos = None
            is_clicked = False
            
            if results.multi_hand_landmarks:
                # Only use the first hand for UI control to avoid confusion
                hand_lms = results.multi_hand_landmarks[0]
                self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                is_clicked, cursor_pos = self.detect_pinch(img, hand_lms)

            # --- STATE MACHINE ---

            # 1. LOGIN SCREEN
            if self.state == "LOGIN":
                cv2.putText(img, "PLEASE ENTER NAME", (400, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                self.keyboard.draw(img, cursor_pos)
                if is_clicked and cursor_pos:
                    res = self.keyboard.handle_click(cursor_pos)
                    if res == "ENTER_PRESSED":
                        self.current_user = self.keyboard.input_text
                        self.db.register_user(self.current_user)
                        self.state = "MENU"

            # 2. MAIN MENU
            elif self.state == "MENU":
                cv2.putText(img, f"Welcome, {self.current_user}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
                
                # Draw Buttons
                for btn in [self.btn_start, self.btn_records, self.btn_exit]:
                    is_hover = btn.is_hovering(*cursor_pos) if cursor_pos else False
                    btn.draw(img, is_hover)
                
                # Logic
                if is_clicked and cursor_pos:
                    if self.btn_start.is_hovering(*cursor_pos): self.state = "DIFFICULTY"
                    elif self.btn_records.is_hovering(*cursor_pos): self.state = "RECORDS"
                    elif self.btn_exit.is_hovering(*cursor_pos): break

            # 3. DIFFICULTY SELECT
            elif self.state == "DIFFICULTY":
                cv2.putText(img, "SELECT DIFFICULTY", (450, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)
                
                for btn in [self.btn_easy, self.btn_med, self.btn_hard, self.btn_back]:
                    is_hover = btn.is_hovering(*cursor_pos) if cursor_pos else False
                    btn.draw(img, is_hover)
                
                if is_clicked and cursor_pos:
                    if self.btn_easy.is_hovering(*cursor_pos):
                        self.set_difficulty("EASY")
                        self.state = "PLAYING"
                    elif self.btn_med.is_hovering(*cursor_pos):
                        self.set_difficulty("NORMAL")
                        self.state = "PLAYING"
                    elif self.btn_hard.is_hovering(*cursor_pos):
                        self.set_difficulty("HARD")
                        self.state = "PLAYING"
                    elif self.btn_back.is_hovering(*cursor_pos):
                        self.state = "MENU"
                    
                    if self.state == "PLAYING":
                        # Reset Game Params
                        self.enemies = []
                        self.score = 0
                        self.last_spawn_time = time.time()

            # 4. PLAYING GAME
            elif self.state == "PLAYING":
                # UI
                cv2.circle(img, self.center, 30, (0, 255, 0), -1)
                cv2.putText(img, f"Score: {self.score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2)
                
                # Logic
                if time.time() - self.last_spawn_time > self.spawn_interval:
                    self.spawn_enemy()
                    self.last_spawn_time = time.time()
                
                for enemy in self.enemies[:]:
                    enemy['x'] += enemy['vx']
                    enemy['y'] += enemy['vy']
                    
                    # Attack Collision
                    if is_clicked and cursor_pos:
                        if math.hypot(enemy['x'] - cursor_pos[0], enemy['y'] - cursor_pos[1]) < (enemy['radius'] + 30):
                            self.enemies.remove(enemy)
                            self.score += 1
                            continue
                            
                    # Base Collision
                    if math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1]) < 40:
                        self.state = "GAME_OVER"
                        self.db.add_score(self.current_user, self.score)
                    
                    cv2.circle(img, (int(enemy['x']), int(enemy['y'])), int(enemy['radius']), enemy['color'], -1)

            # 5. GAME OVER
            elif self.state == "GAME_OVER":
                cv2.putText(img, "GAME OVER", (450, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                cv2.putText(img, f"Final Score: {self.score}", (500, 380), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
                
                is_hover = self.btn_back.is_hovering(*cursor_pos) if cursor_pos else False
                self.btn_back.draw(img, is_hover)
                
                if is_clicked and cursor_pos and self.btn_back.is_hovering(*cursor_pos):
                    self.state = "MENU"

            # 6. RECORDS
            elif self.state == "RECORDS":
                cv2.rectangle(img, (100, 100), (1180, 650), (240, 240, 240), -1)
                cv2.putText(img, "PLAYER RECORDS", (480, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (50, 50, 50), 3)
                
                # Display Current User Stats
                user_data = self.db.data.get(self.current_user, {})
                best = user_data.get("best_score", 0)
                history = user_data.get("history", [])
                
                cv2.putText(img, f"User: {self.current_user}", (150, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
                cv2.putText(img, f"Personal Best: {best}", (150, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,100,0), 2)
                cv2.putText(img, f"Games Played: {len(history)}", (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)

                # Buttons
                self.btn_back_rec.draw(img, self.btn_back_rec.is_hovering(*cursor_pos) if cursor_pos else False)
                self.btn_delete_user.draw(img, self.btn_delete_user.is_hovering(*cursor_pos) if cursor_pos else False)
                
                if is_clicked and cursor_pos:
                    if self.btn_back_rec.is_hovering(*cursor_pos):
                        self.state = "MENU"
                    elif self.btn_delete_user.is_hovering(*cursor_pos):
                        self.db.delete_user(self.current_user)
                        self.keyboard.input_text = "" # Reset input
                        self.state = "LOGIN"

            cv2.imshow("Hand Game Ultimate", img)
            if cv2.waitKey(1) & 0xFF == 27: break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()