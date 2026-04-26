import random

from media.music import Music


class RockAndRoll(Music):

    def __init__(self, sample_rate=44100):
        self._tempo = 160
        self._loop_factor = 3.0
        super().__init__(sample_rate)

    def generate_notes(self):
        self.bass_line = []
        self.rhythm_guitar = []
        self.solo_part = []
        self.accompaniment_part = []
        self.drum_pattern = []

        progression = [
            (40, 0, 4),
            (45, 4, 4),
        ]
        chord_map = [
            (40, 0, 4),
            (45, 4, 2),
            (40, 6, 2),
            (47, 8, 1),
            (45, 9, 1),
            (40, 10, 2),
        ]

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                notes = [root, root+4, root+7, root+10]
                rhythm_times = [
                    (notes[0], beat_base + 0.0, 0.3),
                    (notes[1], beat_base + 0.67, 0.3),
                    (notes[2], beat_base + 1.0, 0.3),
                    (notes[3], beat_base + 1.67, 0.3),
                    (notes[0] + 12, beat_base + 2.0, 0.3),
                    (notes[1] + 12, beat_base + 2.67, 0.3),
                    (notes[2] + 12, beat_base + 3.0, 0.3),
                    (root + 11, beat_base + 3.67, 0.3),
                ]
                self.bass_line.extend(rhythm_times)

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                self.rhythm_guitar.append((root, beat_base + 1, 0.2))
                self.rhythm_guitar.append((root+7, beat_base + 1, 0.2))
                self.rhythm_guitar.append((root, beat_base + 3, 0.2))
                self.rhythm_guitar.append((root+7, beat_base + 3, 0.2))

        total_beats = int(sum(num_bars for _, _, num_bars in chord_map) * 4)
        for beat in range(total_beats):
            bar_pos = beat % 4
            self.drum_pattern.append(('hihat', beat + 0.0))
            self.drum_pattern.append(('hihat', beat + 0.67))
            self.drum_pattern.append(('hihat', beat + 1.0))
            self.drum_pattern.append(('hihat', beat + 1.67))
            self.drum_pattern.append(('hihat', beat + 2.0))
            self.drum_pattern.append(('hihat', beat + 2.67))
            self.drum_pattern.append(('hihat', beat + 3.0))
            self.drum_pattern.append(('hihat', beat + 3.67))

            if bar_pos == 0 or bar_pos == 2:
                self.drum_pattern.append(('kick', beat))
            if bar_pos == 1 or bar_pos == 3:
                self.drum_pattern.append(('snare', beat))

        pentatonic = [64, 67, 69, 70, 71, 72, 74, 76]
        if not hasattr(self, '_random'):
            self._random = random.Random(123)
        solo_dur = 0.25
        for bar_base in range(0, 48, 4):
            for i in range(8):
                t = bar_base + i * 0.5
                note = self._random.choice(pentatonic)
                self.solo_part.append((note, t, solo_dur))

        for root, start_bar, num_bars in chord_map:
            for bar_offset in range(num_bars):
                beat_base = start_bar + bar_offset * 4
                self.accompaniment_part.append((root + 12, beat_base, 3.8))
                self.accompaniment_part.append((root + 19, beat_base, 3.8))
                if root == 40:
                    self.accompaniment_part.append((root + 15, beat_base, 3.8))
                elif root == 45:
                    self.accompaniment_part.append((root + 14, beat_base, 3.8))
                elif root == 47:
                    self.accompaniment_part.append((root + 16, beat_base, 3.8))
