from gui.widget import Widget


class Dropdown(Widget):
    """Simple dropdown widget (combo box)."""
    def __init__(self, label, key, x, y, w, h, options, callback=None):
        self.label = label
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.options = options          # list of (display_text, value)
        self.callback = callback
        self.selected_index = 0
        self.expanded = False

    def set_value(self, value):
        for i, (_, v) in enumerate(self.options):
            if v == value:
                self.selected_index = i
                break

    def get_value(self):
        return self.options[self.selected_index][1]

    def layout(self, x, y, w, row_h, spacing):
        self.x = x
        self.y = y
        self.w = w
        self.h = row_h

    def handle_mouse(self, mx, my, dialog):
        if self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h:
            self.expanded = not self.expanded
            return True
        if self.expanded:
            # check options
            opt_y = self.y + self.h
            for i, (text, _) in enumerate(self.options):
                if self.x <= mx <= self.x + self.w and opt_y <= my <= opt_y + self.h:
                    self.selected_index = i
                    self.expanded = False
                    if self.callback:
                        self.callback(self.get_value())
                    return True
                opt_y += self.h
        return False

    def draw(self, dialog):
        # draw label
        dialog._draw_text(self.label, self.x, self.y + 5, 12, color=(1,1,1,1))
        # draw box
        dialog._draw_rect(self.x + 80, self.y, self.w - 80, self.h, (0.3,0.3,0.3,0.9))
        # draw selected value
        selected_text = self.options[self.selected_index][0]
        dialog._draw_text(selected_text, self.x + 85, self.y + 5, 12, color=(1,1,1,1))
        # draw arrow
        arrow_x = self.x + self.w - 15
        dialog._draw_text("▼", arrow_x, self.y + 3, 14, color=(1,1,1,1))
        # if expanded, draw options
        if self.expanded:
            opt_y = self.y + self.h
            for text, _ in self.options:
                dialog._draw_rect(self.x + 80, opt_y, self.w - 80, self.h, (0.2,0.2,0.2,0.95))
                dialog._draw_text(text, self.x + 85, opt_y + 5, 12, color=(1,1,1,1))
                opt_y += self.h
