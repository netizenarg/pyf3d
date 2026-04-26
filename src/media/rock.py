import random

import numpy

from media.music import Music


class Rock(Music):
    def __init__(self, sample_rate=44100):
        self.chords = [
            (40, 0, 4), (45, 4, 4), (47, 8, 4), (40, 12, 4),
            (40, 16, 4), (45, 20, 4), (47, 24, 4), (40, 28, 4),
            (40, 32, 4), (45, 36, 4), (47, 40, 4), (40, 44, 4),
            (40, 48, 4), (45, 52, 4), (47, 56, 4), (40, 60, 4)
        ]
        self._loop_factor = 3.0
        super().__init__(sample_rate)

    def generate_notes(self):
        self.bass_line = []
        self.rhythm_guitar = []
        self.solo_part = []
        self.accompaniment_part = []
        self.drum_pattern = []
        for root_note, start_beat, length_beats in self.chords:
            self.bass_line.append((root_note, start_beat, length_beats))
            self.bass_line.append((root_note + 12, start_beat + 2, 0.5))
            self.bass_line.append((root_note + 12, start_beat + 3, 0.5))
        for root_note, start_beat, length_beats in self.chords:
            for sub_beat in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
                dur = 0.4
                self.rhythm_guitar.append((root_note, start_beat + sub_beat, dur))
                self.rhythm_guitar.append((root_note + 7, start_beat + sub_beat, dur))
        for beat in range(64):
            if beat % 4 == 0:
                self.drum_pattern.append(('kick', beat))
            if beat % 4 == 2:
                self.drum_pattern.append(('snare', beat))
            self.drum_pattern.append(('hihat', beat))
            self.drum_pattern.append(('hihat', beat + 0.5))
        pentatonic = [64, 67, 69, 71, 72, 74, 76, 79]
        random.seed(42)
        solo_beats = [i * 0.5 for i in range(128)]
        for s in solo_beats:
            self.solo_part.append((random.choice(pentatonic), s, 0.25))
        for root_note, start_beat, length_beats in self.chords:
            self.accompaniment_part.append((root_note + 12, start_beat, length_beats))
            self.accompaniment_part.append((root_note + 19, start_beat, length_beats))
