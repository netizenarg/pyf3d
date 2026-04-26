import logging
import time
import threading


class Album:
    
    def __init__(self):
        self._tracks = []
        self._playing = False
        self._thread = None

    def add(self, music):
        self._tracks.append(music)

    def play(self):
        self._playing = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._playing = False
        for track in self._tracks:
            track.stop()

    def _run(self):
        while self._playing and self._tracks:
            for track in self._tracks:
                while self._playing and track.is_playing:
                    time.sleep(0.5)
                if not self._playing:
                    break
                track.play_one()
                track._loop_finished_event.wait()

