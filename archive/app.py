import cv2
import mediapipe as mp
import math
import random
import time

class HandGame:
    def __init__(self):
        # --- 初始化摄像头 ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280) # 设置宽度
        self.cap.set(4, 720)  # 设置高度

        # --- 初始化 MediaPipe 手部模型 ---
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=2,               # 只追踪一只手，避免混乱
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

        # --- 游戏参数 ---
        self.width = 1280
        self.height = 720
        self.center = (self.width // 2, self.height // 2) # 屏幕中心
        
        self.enemies = []       # 存储敌人的列表
        self.last_spawn_time = 0
        self.spawn_interval = 1.0 # 敌人生成间隔（秒）
        self.score = 0
        self.game_over = False
        self.finger_tip = None  # 手指尖坐标

    def spawn_enemy(self):
        """在屏幕边缘随机生成一个敌人"""
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top':
            x = random.randint(0, self.width)
            y = 0
        elif side == 'bottom':
            x = random.randint(0, self.width)
            y = self.height
        elif side == 'left':
            x = 0
            y = random.randint(0, self.height)
        else: # right
            x = self.width
            y = random.randint(0, self.height)
        
        # 敌人属性: [x, y, speed, radius, color]
        # 计算朝向中心的向量
        angle = math.atan2(self.center[1] - y, self.center[0] - x)
        speed_val = 3 + (self.score * 0.1) # 分数越高速度越快
        vx = math.cos(angle) * speed_val
        vy = math.sin(angle) * speed_val
        
        self.enemies.append({
            'x': x, 'y': y, 
            'vx': vx, 'vy': vy, 
            'radius': 20,
            'color': (0, 0, 255) # 红色
        })

    def update_enemies(self):
        """更新敌人位置并检查碰撞"""
        if self.game_over: return

        for enemy in self.enemies[:]:
            # 1. 移动敌人
            enemy['x'] += enemy['vx']
            enemy['y'] += enemy['vy']

            # 2. 检查是否撞到中间的小人 (Game Over)
            dist_to_center = math.hypot(enemy['x'] - self.center[0], enemy['y'] - self.center[1])
            if dist_to_center < 30: # 假设中心小人半径为30
                self.game_over = True
            
            # 3. 检查是否被手指击中
            if self.finger_tip:
                dist_to_finger = math.hypot(enemy['x'] - self.finger_tip[0], enemy['y'] - self.finger_tip[1])
                if dist_to_finger < (enemy['radius'] + 20): # 20是手指判定的模糊半径
                    self.enemies.remove(enemy)
                    self.score += 1
                    continue

    def draw(self, img):
        # --- 绘制中心小人 (玩家) ---
        color = (0, 255, 0) if not self.game_over else (100, 100, 100)
        cv2.circle(img, self.center, 30, color, -1)
        cv2.putText(img, "Player", (self.center[0]-25, self.center[1]-40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # --- 绘制敌人 ---
        for enemy in self.enemies:
            pos = (int(enemy['x']), int(enemy['y']))
            cv2.circle(img, pos, enemy['radius'], enemy['color'], -1)
            cv2.circle(img, pos, enemy['radius'], (255, 255, 255), 2)

        # --- 绘制UI ---
        cv2.putText(img, f"Score: {self.score}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 0), 3)
        
        if self.game_over:
            cv2.putText(img, "GAME OVER", (self.width//2 - 200, self.height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5)
            cv2.putText(img, "Press 'R' to Restart", (self.width//2 - 150, self.height//2 + 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    def reset_game(self):
        self.enemies = []
        self.score = 0
        self.game_over = False
        self.spawn_interval = 1.0

    def run(self):
        while True:
            success, img = self.cap.read()
            if not success: break

            # 1. 镜像翻转 (让操作更符合直觉)
            img = cv2.flip(img, 1)
            self.height, self.width, _ = img.shape
            self.center = (self.width // 2, self.height // 2)

            # 2. 转换颜色空间供 MediaPipe 使用
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            # 3. 获取手指坐标
            self.finger_tip = None
            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    # 绘制骨架
                    self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                    
                    # 获取食指指尖 (Index 8)
                    lm = hand_lms.landmark[8]
                    cx, cy = int(lm.x * self.width), int(lm.y * self.height)
                    self.finger_tip = (cx, cy)
                    
                    # 在指尖画个圈，表示这是"准星"
                    cv2.circle(img, (cx, cy), 15, (0, 255, 255), -1)

            # 4. 游戏逻辑
            if not self.game_over:
                # 生成敌人
                if time.time() - self.last_spawn_time > self.spawn_interval:
                    self.spawn_enemy()
                    self.last_spawn_time = time.time()
                    # 稍微加快生成速度
                    if self.spawn_interval > 0.4:
                        self.spawn_interval *= 0.98
                
                self.update_enemies()
            else:
                # 游戏结束时的按键检测
                key = cv2.waitKey(1)
                if key == ord('r'):
                    self.reset_game()

            # 5. 渲染
            self.draw(img)

            cv2.imshow("Hand Defender", img)
            
            # 退出检测
            if cv2.waitKey(1) & 0xFF == 27: # ESC键
                break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = HandGame()
    game.run()