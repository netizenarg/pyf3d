class Widget:
    """Base class for all interactive UI widgets."""
    def __init__(self, x, y, w, h):
        self.rect = (x, y, w, h)

    def draw(self, menu):
        """Draw the widget – must be overridden."""
        raise NotImplementedError

    def handle_mouse(self, x, y, menu):
        """Handle mouse click – return True if handled."""
        return False

    def handle_key(self, key, char, dialog=None):
        """Handle keyboard input – return True if handled."""
        return False

    def layout(self, x, y, w, row_h, spacing):
        """Set the widget's position and size (default: full width)."""
        self.rect = (x, y, w, row_h)
