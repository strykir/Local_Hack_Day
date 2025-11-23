import cv2
import mediapipe as mp
import math
import random
import time
import numpy as np

class Button:
    def __init__(self, text, pos, size=(300, 80), color=(200, 200, 200)):
        self.text = text
        self.x, self.y = pos
        self.w, self.h = size
        self.default_color = color
        self.hover_color = (0, 255, 0)
        self.text_color = (50, 50, 50)

    def is_hovering(self, x, y):
        """Check if a point (x, y) is inside the button rect."""
        return self.x < x < self.x + self.w and self.y < y < self.y + self.h

    def draw(self, img, is_hovered=False):
        color = self.hover_color if is_hovered else self.default_color
        
        # Draw rectangle (Button background)
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), color, -1)
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), (255, 255, 255), 3)
        
        # Draw Text (Centered)
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(self.text, font, 1.5, 3)[0]
        text_x = self.x + (self.w - text_size[0]) // 2
        text_y = self.y + (self.h + text_size[1]) // 2
        cv2.putText(img, self.text, (text_x, text_y), font, 1.5, self.text_color, 3)

class HandGame:
    def __init__(self):
        # --- Initialize Camera ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)

        # --- MediaPipe Setup ---
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

        # --- Game Parameters ---
        self.width = 1280
        self.height = 720
        self.center = (self.width // 2, self.height // 2)
        
        # --- State Management ---
        self.state = "MENU" # Options: "MENU", "PLAYING", "GAME_OVER"
        
        # Pinch Logic: Stores boolean status for each hand index to prevent continuous triggering
        # Key: Hand Index (0 or 1), Value: Boolean (True if currently pinching/locked)
        self.hand_clicked_status = {0: False, 1: False}
        self.pinch_threshold = 50

        # --- Game Entities ---
        self.enemies = []
        self.score = 0
        self.spawn_timer = 0
        self.spawn_interval = 0.5

        # --- UI Buttons ---
        # Center button for Start
        btn_x = (self.width - 300) // 2
        btn_y = (self.height - 80) // 2
        self.btn_start = Button("START GAME", (btn_x, btn_y))
        self.btn_restart = Button("RESTART", (btn_x, btn_y))

    def detect_pinch_action(self, img, hand_landmarks, hand_index):
        """
        Calculates pinch distance and handles the 'Debounce' logic.
        Returns: 
            is_click (bool): True ONLY on the frame the pinch happens.
            center (tuple): (x, y) of the pinch center.
        """
        h, w, _ = img.shape
        
        # Get coordinates
        thumb = hand_landmarks.landmark[4]
        index = hand_landmarks.landmark[8]
        
        x4, y4 = int(thumb.x * w), int(thumb.y * h)
        x8, y8 = int(index.x * w), int(index.y * h)
        
        # Calculate Center and Distance
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2
        length = math.hypot(x8 - x4, y8 - y4)

        # Visualization: Connect thumb and index
        cv2.line(img, (x4, y4), (x8, y8), (255, 0, 255), 3)

        is_click = False
        
        # --- State Machine Logic for Pinching ---
        if length < self.pinch_threshold:
            # Current physical state: Pinching
            
            if not self.hand_clicked_status.get(hand_index, False):
                # Previous state: Open
                # Action: TRIGGER CLICK (Just this once)
                is_click = True
                self.hand_clicked_status[hand_index] = True # Lock the state
            else:
                # Previous state: Pinching
                # Action: Do nothing (Player is holding the pinch)
                is_click = False 
            
            # Visual: Green (Closed)
            cv2.circle(img, (cx, cy), 15, (0, 255, 0), -1)
            
        else:
            # Current physical state: Open
            # Action: Reset the lock so player can click again
            self.hand_clicked_status[hand_index] = False
            
            # Visual: Red (Open)
            cv2.circle(img, (cx, cy), 15, (0, 0, 255), 2)

        return is_click, (cx, cy)

    def spawn_enemy(self):
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top':    x, y = random.randint(0, self.width), 0
        elif side == 'bottom': x, y = random.randint(0, self.width), self.height
        elif side == 'left':   x, y = 0, random.randint(0, self.height)
        else:                x, y = self.width, random.randint(0, self.height)
        
        angle = math.atan2(self.center[1] - y, self.center[0] - x)
        speed_val = 4 + (self.score * 0.15)
        
        self.enemies.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed_val,
            'vy': math.sin(angle) * speed_val,
            'radius': 25,
            'color': (0, 0, 255)
        })

    def run(self):
        while True:
            success, img = self.cap.read()
            if not success: break

            # 1. Flip & Prepare
            img = cv2.flip(img, 1)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            # 2. Collect Clicks from all hands
            # List of coordinates where a VALID click happened this frame
            valid_clicks = [] 
            cursor_positions = [] # Just for hovering effect

            if results.multi_hand_landmarks:
                for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                    self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                    
                    # Call the dedicated function
                    clicked, pos = self.detect_pinch_action(img, hand_lms, idx)
                    
                    cursor_positions.append(pos)
                    if clicked:
                        valid_clicks.append(pos)

            # 3. State Management
            
            # --- MENU STATE ---
            if self.state == "MENU":
                # Check Hover
                is_hovered = any(self.btn_start.is_hovering(x, y) for x, y in cursor_positions)
                self.btn_start.draw(img, is_hovered)
                
                # Check Click
                for cx, cy in valid_clicks:
                    if self.btn_start.is_hovering(cx, cy):
                        self.state = "PLAYING"
                        self.score = 0
                        self.enemies = []
                        self.spawn_interval = 1.0
                        self.spawn_timer = time.time()

            # --- PLAYING STATE ---
            elif self.state == "PLAYING":
                # Draw Player
                cv2.circle(img, self.center, 30, (0, 255, 0), -1)
                cv2.putText(img, f"Score: {self.score}", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 0), 3)

                # Spawn Enemies
                if time.time() - self.spawn_timer > self.spawn_interval:
                    self.spawn_enemy()
                    self.spawn_timer = time.time()
                    if self.spawn_interval > 0.4: self.spawn_interval *= 0.99

                # Update Enemies
                for enemy in self.enemies[:]:
                    enemy['x'] += enemy['vx']
                    enemy['y'] += enemy['vy']
                    
                    # Collision: Player
                    dist_center = math.hypot(enemy['x']-self.center[0], enemy['y']-self.center[1])
                    if dist_center < 40:
                        self.state = "GAME_OVER"
                    
                    # Collision: Player Clicks (Attacks)
                    hit = False
                    for cx, cy in valid_clicks:
                        dist_click = math.hypot(enemy['x']-cx, enemy['y']-cy)
                        if dist_click < (enemy['radius'] + 30):
                            self.enemies.remove(enemy)
                            self.score += 1
                            # Draw explosion effect (simple circles)
                            cv2.circle(img, (int(enemy['x']), int(enemy['y'])), 40, (255, 255, 0), 2)
                            hit = True
                            break
                    
                    if not hit:
                        # Draw Enemy
                        cv2.circle(img, (int(enemy['x']), int(enemy['y'])), int(enemy['radius']), enemy['color'], -1)

            # --- GAME OVER STATE ---
            elif self.state == "GAME_OVER":
                # Draw Game Over Text
                cv2.putText(img, "GAME OVER", (self.width//2 - 200, self.height//2 - 100), 
                           cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5)
                
                # Check Hover
                is_hovered = any(self.btn_restart.is_hovering(x, y) for x, y in cursor_positions)
                self.btn_restart.draw(img, is_hovered)

                # Check Click
                for cx, cy in valid_clicks:
                    if self.btn_restart.is_hovering(cx, cy):
                        self.state = "PLAYING"
                        self.score = 0
                        self.enemies = []
                        self.spawn_timer = time.time()

            cv2.imshow("Hand Game UI", img)
            if cv2.waitKey(1) & 0xFF == 27: break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()
