from gui.widget import Widget


class NumberBox(Widget):
    def __init__(self, label, config_key, x, y, w, h, min_val, max_val, step, callback=None, mode='decimal'):
        super().__init__(x, y, w, h)
        self.label = label
        self.key = config_key
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.callback = callback
        self.mode = mode
        self.active = False
        self.input_buffer = ""
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
        widget._draw_rect(x, y, w, h, color=(0.5, 0.5, 0.5, 0.9))
        widget._draw_text(self.label, x + 5, y + (h - 12)//2, 12, color=(1,1,1,1), uppercase=True)

        if self.active:
            val_str = self.input_buffer
        else:
            val = widget.config.get(self.key, 0)
            val_str = str(int(val)) if self.mode == 'integer' else f"{val:.1f}"

        value_w = 80
        value_x = x + w - 130
        widget._draw_rect(value_x, y + 2, value_w, h - 4, (1,1,1,0.9))
        display_text = val_str + ("|" if self.active and (len(val_str) % 2 == 0) else "")
        widget._draw_text(display_text, value_x + 5, y + (h - 12)//2, 12, color=(0,0,0,1), uppercase=False)

        widget._draw_text("+", self.inc_rect[0] + 8, self.inc_rect[1] + (h - 12)//2, 12, color=(1,1,1,1), uppercase=False)
        widget._draw_text("-", self.dec_rect[0] + 8, self.dec_rect[1] + (h - 12)//2, 12, color=(1,1,1,1), uppercase=False)

    def handle_mouse(self, x, y, widget):
        if self.inc_rect is None:
            self._update_button_rects()
        ix, iy, iw, ih = self.inc_rect
        dx, dy, dw, dh = self.dec_rect
        value_w = 80
        value_x = self.rect[0] + self.rect[2] - 130
        if value_x <= x <= value_x + value_w and self.rect[1] <= y <= self.rect[1] + self.rect[3]:
            if not self.active:
                self.active = True
                val = widget.config.get(self.key, 0)
                self.input_buffer = str(int(val)) if self.mode == 'integer' else f"{val:.1f}"
            return True
        else:
            if self.active:
                self._apply_input(widget)
                self.active = False
        if ix <= x <= ix + iw and iy <= y <= iy + ih:
            new_val = min(self.max_val, widget.config[self.key] + self.step)
            widget.config[self.key] = new_val
            if self.callback:
                self.callback(new_val)
            self.active = False
            return True
        elif dx <= x <= dx + dw and dy <= y <= dy + dh:
            new_val = max(self.min_val, widget.config[self.key] - self.step)
            widget.config[self.key] = new_val
            if self.callback:
                self.callback(new_val)
            self.active = False
            return True
        return False

    def handle_key(self, key, char, dialog):
        if not self.active:
            return False
        if key == 259:
            self.input_buffer = self.input_buffer[:-1]
        elif key == 257 or key == 335:
            self._apply_input(dialog)
            self.active = False
        elif char:
            if char.isdigit() or char == '-' or (self.mode == 'decimal' and char == '.'):
                self.input_buffer += char
        return True

    def _apply_input(self, dialog):
        if not self.input_buffer:
            return
        try:
            if self.mode == 'integer':
                val = int(float(self.input_buffer))
            else:
                val = float(self.input_buffer)
            val = max(self.min_val, min(self.max_val, val))
            dialog.config[self.key] = val
            if self.callback:
                self.callback(val)
        except ValueError:
            pass
