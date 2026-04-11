from gui.widget import Widget


class CheckBox(Widget):
    def __init__(self, label, config_key, x, y, w, h, callback=None):
        super().__init__(x, y, w, h)
        self.label = label
        self.key = config_key
        self.callback = callback

    def draw(self, widget):
        x, y, w, h = self.rect
        box_size = min(h, 20)
        # Box background
        widget._draw_rect(x, y, box_size, h, color=(0.5, 0.5, 0.5, 0.9))
        # Check mark
        if widget.config.get(self.key, False):
            widget._draw_rect(x + 2, y + 2, box_size - 4, h - 4, color=(0.2, 0.8, 0.2, 0.9))
        # Label
        label_x = x + box_size + 5
        label_y = y + (h - 12) // 2
        widget._draw_text(self.label, label_x, label_y, 12, color=(1, 1, 1, 1))

    def handle_mouse(self, x, y, widget):
        rx, ry, rw, rh = self.rect
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            new_val = not widget.config.get(self.key, False)
            widget.config[self.key] = new_val
            if self.callback:
                self.callback(new_val)
            return True
        return False
