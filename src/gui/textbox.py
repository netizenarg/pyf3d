from gui.widget import Widget


class TextBox(Widget):
    def __init__(self, label, config_key, x, y, w, h, callback=None, label_width=100):
        super().__init__(x, y, w, h)
        self.label = label
        self.key = config_key
        self.callback = callback
        self.active = False
        self.text = ""
        self.label_width = label_width

    def set_text(self, text):
        self.text = text

    def get_text(self):
        return self.text

    def handle_mouse(self, x, y, widget):
        rx, ry, rw, rh = self.rect
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            self.active = True
            return True
        else:
            self.active = False
            return False

    def handle_key(self, key, char, dialog=None):
        if not self.active:
            return False
        if key == 259:
            if self.text:
                self.text = self.text[:-1]
        elif key == 257 or key == 335:
            self.active = False
        elif char and 32 <= ord(char) <= 126:
            self.text += char
        else:
            return False
        if self.callback:
            self.callback(self.text)
        return True

    def draw(self, dialog):
        rx, ry, rw, rh = self.rect
        dialog._draw_text(self.label, rx, ry + 5, 12, color=(1,1,1,1))
        box_x = rx + self.label_width
        box_w = rw - self.label_width
        dialog._draw_rect(box_x, ry, box_w, rh, (1,1,1,0.9))
        display_text = self.text if self.text else ""
        if self.active:
            display_text += "|"
        dialog._draw_text(display_text, box_x + 5, ry + 5, 12, color=(0,0,0,1))
