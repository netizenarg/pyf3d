import random
import math

from media.music import Music


class Jazz(Music):

    def __init__(self, sample_rate=44100):
        self._tempo = 140
        self._total_beats = 96.0
        self._loop_factor = 3.0
        super().__init__(sample_rate)

    def generate_notes(self):
        self.bass_line = []
        self.rhythm_guitar = []
        self.solo_part = []
        self.accompaniment_part = []
        self.drum_pattern = []

        bar_12 = [
            (58, 0, 4),    # Bb7
            (63, 4, 2),    # Eb7
            (58, 6, 2),    # Bb7
            (58, 8, 1),    # Bb7
            (63, 9, 1),    # Eb7
            (58, 10, 2),   # Bb7
            (60, 12, 2),   # Cm7
            (65, 14, 2),   # F7
            (58, 16, 2),   # Bb7
            (63, 18, 2),   # Eb7
            (58, 20, 2),   # Bb7
            (65, 22, 2),   # F7
        ]
        chord_map = bar_12

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                notes = [root, root+4, root+7, root+10]
                self.bass_line.extend([
                    (notes[0], beat_base, 0.9),
                    (notes[1], beat_base + 1, 0.9),
                    (notes[2], beat_base + 2, 0.9),
                    (notes[3], beat_base + 3, 0.9),
                ])

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                self.rhythm_guitar.append((root+4, beat_base + 1, 0.3))
                self.rhythm_guitar.append((root+10, beat_base + 1, 0.3))
                self.rhythm_guitar.append((root+4, beat_base + 3, 0.3))
                self.rhythm_guitar.append((root+10, beat_base + 3, 0.3))

        total_beats = int(sum(num_bars for _, _, num_bars in chord_map) * 4)
        for beat in range(total_beats):
            bar_pos = beat % 4
            self.drum_pattern.append(('hihat', beat))
            self.drum_pattern.append(('hihat', beat + 0.67))
            if bar_pos == 0 or bar_pos == 2:
                self.drum_pattern.append(('kick', beat))
            if bar_pos == 1 or bar_pos == 3:
                self.drum_pattern.append(('snare', beat))

        blues_scale = [58, 61, 63, 64, 65, 68, 70]
        if not hasattr(self, '_random'):
            self._random = random.Random(999)
        solo_dur = 0.25
        for beat_pos in range(int(total_beats * 4)):
            t = beat_pos * 0.25
            note = self._random.choice(blues_scale)
            self.solo_part.append((note, t, solo_dur))

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                self.accompaniment_part.append((root, beat_base, 3.8))
                self.accompaniment_part.append((root+4, beat_base, 3.8))
                self.accompaniment_part.append((root+7, beat_base, 3.8))
                self.accompaniment_part.append((root+10, beat_base, 3.8))
