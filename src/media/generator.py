import math
import random
import logging


class Generator:
    """Generate sound buffers (lists of float samples) without external libraries."""

    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

    def generate_sine(self, frequency, duration, volume=0.5):
        """Generate a sine wave buffer."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        for i in range(num_samples):
            t = i / self.sample_rate
            value = volume * math.sin(2.0 * math.pi * frequency * t)
            samples.append(value)
        return samples

    def generate_white_noise(self, duration, volume=0.3):
        """Generate white noise buffer."""
        num_samples = int(self.sample_rate * duration)
        samples = [volume * (random.random() * 2 - 1) for _ in range(num_samples)]
        return samples

    def generate_random_sine_sweep(self, duration, volume=0.5, min_freq=200, max_freq=2000):
        """Generate a sine wave with randomly changing frequency every 0.1 seconds."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        segment_duration = 0.1  # seconds
        segment_samples = int(self.sample_rate * segment_duration)

        for start in range(0, num_samples, segment_samples):
            freq = random.uniform(min_freq, max_freq)
            end = min(start + segment_samples, num_samples)
            for i in range(start, end):
                t = i / self.sample_rate
                # phase continuous: use local time within segment
                local_t = (i - start) / self.sample_rate
                value = volume * math.sin(2.0 * math.pi * freq * local_t)
                samples.append(value)
        return samples

    def generate_random(self, duration, volume=0.5, mode='noise', **kwargs):
        """
        Generate a random sound buffer.

        Parameters:
            duration (float): length in seconds
            volume (float): amplitude (0.0 to 1.0)
            mode (str): 'noise' (white noise) or 'sweep' (random frequency sine sweep)
            **kwargs: additional arguments for specific modes
        """
        if mode == 'noise':
            return self.generate_white_noise(duration, volume)
        elif mode == 'sweep':
            min_freq = kwargs.get('min_freq', 200)
            max_freq = kwargs.get('max_freq', 2000)
            #logging.debug(f"sound buffer generate_random({duration}, {volume}, {mode})")
            return self.generate_random_sine_sweep(duration, volume, min_freq, max_freq)
        else:
            logging.error(f"Unsupported mode: {mode}. Use 'noise' or 'sweep'.")
