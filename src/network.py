import json
import threading
import queue
import logging
from typing import Optional, Tuple, Any
import numpy

class NetworkClient:
    """Fetches chunk data from a remote server."""
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        import requests  # lazy import, not always needed
        while True:
            cx, cz = self.request_queue.get()
            if cx is None:
                break
            try:
                resp = requests.get(f"{self.server_url}/chunk/{cx}/{cz}", timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Convert JSON back to numpy arrays
                    vertices = numpy.array(data['vertices'], dtype=numpy.float32).reshape(-1, 6)
                    indices = numpy.array(data['indices'], dtype=numpy.uint32)
                    trees = data['trees']  # list of dicts
                    self.response_queue.put((cx, cz, vertices, indices, trees))
                else:
                    self.response_queue.put((cx, cz, None, None, None))
            except Exception as e:
                logging.error(f"Network error for chunk ({cx},{cz}): {e}")
                self.response_queue.put((cx, cz, None, None, None))

    def request_chunk(self, cx: int, cz: int):
        self.request_queue.put((cx, cz))

    def get_completed(self):
        completed = []
        while True:
            try:
                completed.append(self.response_queue.get_nowait())
            except queue.Empty:
                break
        return completed

    def stop(self):
        self.request_queue.put((None, None))
