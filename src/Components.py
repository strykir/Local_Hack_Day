import cv2

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

    def draw_on_overlay(self, overlay, is_hovered=False):
        color = self.hover_color if is_hovered else self.color
        cv2.rectangle(overlay, (self.x, self.y), (self.x + self.w, self.y + self.h), color, -1)
        
    def draw_text_and_border(self, img):
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h), (50, 50, 50), 2)
        font = cv2.FONT_HERSHEY_TRIPLEX 
        scale = self.text_scale
        text_size = cv2.getTextSize(self.text, font, scale, 2)[0]
        while text_size[0] > self.w - 20: 
            scale -= 0.1
            text_size = cv2.getTextSize(self.text, font, scale, 2)[0]
        
        text_x = self.x + (self.w - text_size[0]) // 2
        text_y = self.y + (self.h + text_size[1]) // 2
        cv2.putText(img, self.text, (text_x, text_y), font, scale, (0,0,0), 2)

class VirtualKeyboard:
    def __init__(self, start_x, start_y):
        self.keys = []
        self.input_text = ""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, char in enumerate(chars):
            row = i // 7
            col = i % 7
            x = start_x + col * 70
            y = start_y + row * 70
            self.keys.append(Button(char, (x, y), (60, 60), text_scale=0.8))
        self.btn_del = Button("DEL", (start_x, start_y + 280), (130, 60))
        self.btn_enter = Button("ENTER", (start_x + 140, start_y + 280), (200, 60))

    def draw(self, img, overlay, cursor_positions):
        cv2.rectangle(overlay, (400, 100), (880, 180), (255, 255, 255), -1)
        buttons = self.keys + [self.btn_del, self.btn_enter]
        for btn in buttons:
            is_hover = any(btn.is_hovering(*pos) for pos in cursor_positions)
            btn.draw_on_overlay(overlay, is_hover)
            
    def draw_text(self, img):
        cv2.rectangle(img, (400, 100), (880, 180), (0, 0, 0), 2)
        cv2.putText(img, self.input_text + "|", (420, 160), cv2.FONT_HERSHEY_TRIPLEX , 1.5, (0,0,0), 3)
        buttons = self.keys + [self.btn_del, self.btn_enter]
        for btn in buttons:
            btn.draw_text_and_border(img)

    def handle_click(self, pos):
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