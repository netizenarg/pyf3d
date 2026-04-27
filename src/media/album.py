import logging
import threading
import time


class Album:
    def __init__(self):
        self._tracks = []
        self._playing = False
        self._thread = None
        self._current_index = 0

    def add(self, music):
        self._tracks.append(music)

    def play(self):
        self._playing = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def pause(self):
        if self._tracks:
            idx = self._current_index % len(self._tracks)
            track = self._tracks[idx]
            track.stop()
        self._playing = False
        logging.debug(f'Album is pausing')

    def resume(self):
        if not self._playing:
            self._playing = True
            self.play()
        logging.debug(f'Album is continuing')

    def stop(self, finish=False):
        self._playing = False
        for track in self._tracks:
            track.stop()
        if finish:
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(1)
            self._tracks = None
        logging.debug(f'Album is stopped')

    def _run(self):
        logging.debug(f'Album is playing')
        while self._playing and self._tracks:
            idx = self._current_index % len(self._tracks)
            track = self._tracks[idx]
            track.play_one()
            track._loop_finished_event.wait()
            while not self._playing:
                time.sleep(1)
                continue
            self._current_index += 1
