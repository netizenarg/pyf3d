from gui.numberbox import NumberBox


class Tab:
    """A tab containing a list of widgets."""
    def __init__(self, name):
        self.name = name
        self.widgets = []

    def add_widget(self, widget):
        self.widgets.append(widget)

    def layout(self, x, y, width, row_height, spacing):
        """Assign positions to all widgets in a vertical list."""
        current_y = y
        for w in self.widgets:
            # All widgets span the full width
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
