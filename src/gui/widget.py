
class Widget:
    """Base class for all interactive UI widgets."""
    def __init__(self, x, y, w, h):
        self.rect = (x, y, w, h)

    def draw(self, menu):
        raise NotImplementedError

    def handle_mouse(self, x, y, menu):
        return False
