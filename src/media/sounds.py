import logging
import math

from media.audio import Audio


class Sound:
    """Base class for all sound effects. Stores pre‑generated samples."""
    def __init__(self):
        self.audio = Audio()
        self.samples = []   # list of float samples

    def play(self, volume=1.0, sample_rate=44100):
        """Play the stored sound effect in a background thread."""
        if self.samples:
            self.audio.play_thread(self.samples, sample_rate=sample_rate, volume=volume)


class Shot(Sound):
    """Short high‑frequency sweep – gunshot feel."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 0.08
        vol = 0.2
        self.samples = gen.generate_random_sine_sweep(duration, volume=vol, min_freq=800, max_freq=600)

        
class LowShot(Sound):
    """Deep, low‑frequency shot – heavy weapon feel."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 0.15
        vol = 0.8
        # low frequency sweep from 80 Hz down to 40 Hz, mixed with a bit of rumble
        sweep = gen.generate_random_sine_sweep(duration, volume=vol, min_freq=300, max_freq=500)
        noise = gen.generate_white_noise(duration, volume=vol * 0.3)
        # combine and clip
        self.samples = [
            max(-1.0, min(1.0, s + n))
            for s, n in zip(sweep, noise)
        ]


class Explosion(Sound):
    """Rumble with white noise – explosion."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 0.5
        vol = 0.7
        sweep = gen.generate_random_sine_sweep(duration, volume=vol, min_freq=40, max_freq=200)
        noise = gen.generate_white_noise(duration, volume=vol * 0.5)
        self.samples = [s + n for s, n in zip(sweep, noise)]


class Hit(Sound):
    """Short impulse – impact hit."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 0.5
        vol = 0.5
        self.samples = gen.generate_white_noise(duration, volume=vol)


class Groan(Sound):
    """Low frequency, slowly decaying tone – zombie groan."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 1.0
        freq = 90
        vol = 0.6
        num = int(gen.sample_rate * duration)
        samples = []
        for i in range(num):
            t = i / gen.sample_rate
            env = 1.0 - (i / num)
            samples.append(vol * env * (math.sin(2 * math.pi * freq * t) 
                                        + 0.2 * math.sin(2 * math.pi * freq * 1.5 * t)))
        self.samples = samples


class Damage(Sound):
    """Noise burst – receiving damage."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        duration = 0.5
        vol = 0.3
        samples = gen.generate_white_noise(duration, volume=vol)
        # add a sharp click at start
        click_len = int(0.02 * gen.sample_rate)
        for i in range(min(click_len, len(samples))):
            samples[i] += 0.8
        self.samples = samples


class LevelUp(Sound):
    """Ascending three‑note sequence – level up fanfare."""
    def __init__(self):
        super().__init__()
        gen = self.audio.generator
        note_dur = 0.15
        gap = 0.05
        freqs = [523.25, 659.25, 783.99]  # C5, E5, G5
        total_dur = 3 * (note_dur + gap)
        num = int(gen.sample_rate * total_dur)
        samples = [0.0] * num
        for idx, freq in enumerate(freqs):
            start_i = int(gen.sample_rate * (idx * (note_dur + gap)))
            end_i = start_i + int(gen.sample_rate * note_dur)
            for i in range(start_i, min(end_i, num)):
                t = (i - start_i) / gen.sample_rate
                samples[i] += 0.4 * math.sin(2 * math.pi * freq * t)
        self.samples = samples
