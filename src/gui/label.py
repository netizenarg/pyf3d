from gui.widget import Widget


class Label(Widget):
    """Read‑only text label."""
    def __init__(self, label, key, x, y, w, h, getter=None):
        self.label = label
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.getter = getter   # function that returns current value

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
        dialog._draw_text(str(value), self.x + 80, self.y + 5, 12, color=(0.8,0.8,0.8,1))
