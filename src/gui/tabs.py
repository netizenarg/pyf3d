from gui.numberbox import NumberBox


class Tab:
    def __init__(self, name):
        self.name = name
        self.widgets = []

    def add_widget(self, widget):
        self.widgets.append(widget)

    def layout(self, x, y, width, row_height, spacing):
        current_y = y
        for w in self.widgets:
            if hasattr(w, 'layout') and callable(w.layout):
                w.layout(x, current_y, width, row_height, spacing)
            else:
                w.rect = (x, current_y, width, row_height)
            if isinstance(w, NumberBox):
                w._update_button_rects()
            current_y += row_height + spacing

    def draw(self, widget):
        for w in self.widgets:
            w.draw(widget)

    def handle_mouse(self, x, y, widget):
        for w in self.widgets:
            if w.handle_mouse(x, y, widget):
                return True
        return False

    def handle_key(self, key, char, dialog):
        for w in self.widgets:
            if hasattr(w, 'handle_key') and callable(w.handle_key):
                if w.handle_key(key, char, dialog):
                    return True
        return False
