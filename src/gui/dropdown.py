from gui.widget import Widget


class Dropdown(Widget):
    def __init__(self, label, key, x, y, w, h, options, callback=None, label_width=80):
        self.label = label
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label_width = label_width
        self.options = options
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
        dialog._draw_text(self.label, self.x, self.y + 5, 12, color=(1,1,1,1))
        box_x = self.x + self.label_width
        box_w = self.w - self.label_width
        dialog._draw_rect(box_x, self.y, box_w, self.h, (1,1,1,0.95))
        selected_text = self.options[self.selected_index][0]
        dialog._draw_text(selected_text, box_x + 5, self.y + 5, 12, color=(0,0,0,1))
        arrow_x = box_x + box_w - 15
        dialog._draw_text("▼", arrow_x, self.y + 3, 14, color=(0,0,0,1))
        if self.expanded:
            opt_y = self.y + self.h
            for text, _ in self.options:
                dialog._draw_rect(box_x, opt_y, box_w, self.h, (1,1,1,0.95))
                dialog._draw_text(text, box_x + 5, opt_y + 5, 12, color=(0,0,0,1))
                opt_y += self.h
