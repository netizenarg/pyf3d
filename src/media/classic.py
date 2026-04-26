import random

from .music import Music


class Classic(Music):
    def __init__(self, sample_rate=44100):
        self._tempo = 100
        self._total_beats = 256.0
        self._loop_factor = 3.0
        super().__init__(sample_rate)

    def generate_notes(self):
        self.bass_line = []
        self.rhythm_guitar = []
        self.solo_part = []
        self.accompaniment_part = []
        self.drum_pattern = []

        chord_map = [
            (60, 0, 4), (65, 4, 4), (67, 8, 4), (60, 12, 4),
            (57, 16, 4), (64, 20, 4), (62, 24, 4), (67, 28, 4),
            (60, 32, 4), (65, 36, 4), (67, 40, 4), (60, 44, 4),
            (69, 48, 2), (64, 50, 2), (71, 52, 2), (66, 54, 2),
            (67, 56, 4), (67, 60, 4), (60, 64, 4),
        ]
        final_section = [
            (69, 48, 2), (64, 50, 2), (71, 52, 2), (66, 54, 2),
            (67, 56, 4), (67, 60, 4), (62, 48, 0),
        ]
        chord_map = [
            (60, 0, 4), (65, 4, 4), (67, 8, 4), (60, 12, 4),
            (57, 16, 4), (64, 20, 4), (62, 24, 4), (67, 28, 4),
            (60, 32, 4), (65, 36, 4), (67, 40, 4), (60, 44, 4),
            (62, 48, 2), (67, 50, 2), (60, 52, 4), (62, 56, 2),
            (67, 58, 2), (60, 60, 4), (65, 48, 0),
        ]
        progression = [
            (60, 0), (65, 4), (67, 8), (60, 12),
            (57, 16), (64, 20), (62, 24), (67, 28),
            (60, 32), (65, 36), (67, 40), (60, 44),
            (69, 48), (64, 52), (71, 56), (66, 60),
        ]
        chord_map = []
        for root, start_bar in progression:
            chord_map.append((root, start_bar, 4))

        for root, start_bar, num_bars in chord_map:
            for bar in range(num_bars):
                beat = start_bar + bar * 4
                self.bass_line.append((root, beat, 3.8))

        for root, start_bar, num_bars in chord_map:
            for bar in range(num_bars):
                beat = start_bar + bar * 4
                self.rhythm_guitar.extend([
                    (root, beat, 0.8),
                    (root+4, beat+1, 0.8),
                    (root+7, beat+2, 0.8),
                    (root+12, beat+3, 0.8),
                ])

        melody_data = [
            (60, 0.0, 0.25), (64, 1.0, 0.25), (67, 2.0, 0.5), (69, 3.0, 0.25),
            (67, 4.0, 0.25), (64, 5.0, 0.5), (62, 6.0, 0.25), (60, 7.0, 0.25),
            (65, 8.0, 0.25), (69, 9.0, 0.25), (72, 10.0, 0.5), (71, 11.0, 0.25),
            (69, 12.0, 0.25), (67, 13.0, 0.5), (65, 14.0, 0.25), (64, 15.0, 0.25),
        ]
        total_beats = int(self._total_beats)
        if not hasattr(self, '_random'):
            self._random = random.Random(42)
        for rep in range(8):
            trans = (rep % 2) * 2
            for note, offset, dur in melody_data:
                t = offset + rep * 16
                if t + dur <= total_beats:
                    self.solo_part.append((note + trans, t, dur))

        for root, start_bar, num_bars in chord_map:
            for bar in range(num_bars):
                beat = start_bar + bar * 4
                if bar % 2 == 0:
                    self.accompaniment_part.extend([
                        (root, beat, 1.8),
                        (root+4, beat, 1.8),
                        (root+7, beat, 1.8),
                    ])

        for beat in range(total_beats):
            bar_pos = beat % 4
            if bar_pos == 0 or bar_pos == 2:
                self.drum_pattern.append(('kick', beat))
            if bar_pos == 1 or bar_pos == 3:
                self.drum_pattern.append(('hihat', beat + 0.5))
