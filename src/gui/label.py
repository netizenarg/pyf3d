from gui.widget import Widget


class Label(Widget):
    def __init__(self, label, key, x, y, w, h, getter=None, label_width=80):
        self.label = label
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label_width = label_width
        self.getter = getter

    def layout(self, x, y, w, row_h, spacing):
        self.x = x
        self.y = y
        self.w = w
        self.h = row_h

    def handle_mouse(self, mx, my, dialog):
        return False

    def draw(self, dialog):
        dialog._draw_text(self.label, self.x, self.y + 5, 12, color=(1,1,1,1))
        value = self.getter() if self.getter else ""
        value_x = self.x + self.label_width
        dialog._draw_text(str(value), value_x, self.y + 5, 12, color=(0.8,0.8,0.8,1))
