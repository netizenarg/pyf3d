import glfw
from OpenGL.GL import *

from gui.widget import Widget


class MessageBox(Widget):
    """Simple message box with buttons (Ok, Cancel, Apply)."""
    def __init__(self, title, message, buttons=("Ok",), callback=None):
        super().__init__(0, 0, 400, 200)
        self.title = title
        self.message = message
        self.buttons = buttons
        self.callback = callback
        self.active = False
        self.result = None
        self.width = 400
        self.height = 200
        self.x = 0
        self.y = 0

    def show(self, screen_width, screen_height):
        self.active = True
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        self.rect = (self.x, self.y, self.width, self.height)

    def close(self):
        self.active = False
        if self.callback and self.result is not None:
            self.callback(self.result)

    def handle_mouse(self, x, y, button, dialog):
        if not self.active or button != glfw.MOUSE_BUTTON_LEFT:
            return False
        button_w = 80
        button_h = 30
        button_y = self.y + self.height - button_h - 20
        total = len(self.buttons)
        total_w = total * button_w + (total - 1) * 10
        start_x = self.x + (self.width - total_w) // 2
        for i, label in enumerate(self.buttons):
            bx = start_x + i * (button_w + 10)
            if bx <= x <= bx + button_w and button_y <= y <= button_y + button_h:
                self.result = label
                self.close()
                return True
        return False

    def draw(self, dialog):
        if not self.active:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Dim background
        dialog._draw_rect(0, 0, dialog.width, dialog.height, (0, 0, 0, 0.5))
        # Panel
        dialog._draw_rect(self.x, self.y, self.width, self.height, (0.2, 0.2, 0.2, 0.95))
        # Title bar
        dialog._draw_rect(self.x, self.y, self.width, 30, (0.3, 0.3, 0.3, 0.95))
        dialog._draw_text(self.title, self.x + 10, self.y + 8, 14, (1,1,1,1))
        # Message lines
        lines = self.message.split('\n')
        y_offset = self.y + 50
        for line in lines:
            dialog._draw_text(line, self.x + 20, y_offset, 12, (1,1,1,1))
            y_offset += 20
        # Buttons
        button_w = 80
        button_h = 30
        button_y = self.y + self.height - button_h - 20
        total = len(self.buttons)
        total_w = total * button_w + (total - 1) * 10
        start_x = self.x + (self.width - total_w) // 2
        for i, label in enumerate(self.buttons):
            bx = start_x + i * (button_w + 10)
            dialog._draw_rect(bx, button_y, button_w, button_h, (0.5, 0.5, 0.5, 0.9))
            label_x = bx + (button_w - len(label) * 8) // 2
            dialog._draw_text(label, label_x, button_y + 8, 12, (1,1,1,1))
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)