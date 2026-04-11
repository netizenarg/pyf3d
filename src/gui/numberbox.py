from gui.widget import Widget


class NumberBox(Widget):
    """A setting with a label, current value, and +/- buttons."""
    def __init__(self, label, config_key, x, y, w, h, min_val, max_val, step, callback=None):
        super().__init__(x, y, w, h)
        self.label = label
        self.key = config_key
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.callback = callback   # callback(new_value)
        # Button rects (relative to the widget's right side)
        self.inc_rect = None
        self.dec_rect = None

    def _update_button_rects(self):
        x, y, w, h = self.rect
        self.inc_rect = (x + w - 50, y, 25, h)
        self.dec_rect = (x + w - 25, y, 25, h)

    def draw(self, widget):
        if self.inc_rect is None:
            self._update_button_rects()
        x, y, w, h = self.rect
        # Draw background for the whole row (optional, for visual grouping)
        widget._draw_rect(x, y, w, h, color=(0.5, 0.5, 0.5, 0.9))
        # Draw label
        widget._draw_text(self.label, x + 5, y + (h - 12)//2, 12, color=(1,1,1,1), uppercase=True)
        # Draw current value
        val_str = f"{widget.config[self.key]:.1f}"
        widget._draw_text(val_str, x + w - 110, y + (h - 12)//2, 12, color=(1,1,1,1), uppercase=False)
        # Draw '+' and '-' buttons
        widget._draw_text("+", self.inc_rect[0] + 8, self.inc_rect[1] + (h - 12)//2, 12, color=(1,1,1,1), uppercase=False)
        widget._draw_text("-", self.dec_rect[0] + 8, self.dec_rect[1] + (h - 12)//2, 12, color=(1,1,1,1), uppercase=False)

    def handle_mouse(self, x, y, widget):
        if self.inc_rect is None:
            self._update_button_rects()
        ix, iy, iw, ih = self.inc_rect
        dx, dy, dw, dh = self.dec_rect
        if ix <= x <= ix + iw and iy <= y <= iy + ih:
            new_val = min(self.max_val, widget.config[self.key] + self.step)
            widget.config[self.key] = new_val
            if self.callback:
                self.callback(new_val)
            return True
        elif dx <= x <= dx + dw and dy <= y <= dy + dh:
            new_val = max(self.min_val, widget.config[self.key] - self.step)
            widget.config[self.key] = new_val
            if self.callback:
                self.callback(new_val)
            return True
        return False
