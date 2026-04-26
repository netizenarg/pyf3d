import logging
import threading
import time
import concurrent.futures
import math
import random

import numpy

from media.audio import Audio


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

def _adsr_envelope(num_samples, attack=0.01, decay=0.05, sustain=0.7, release=0.1):
    attack_len = int(attack * num_samples)
    decay_len = int(decay * num_samples)
    release_len = int(release * num_samples)
    sustain_len = num_samples - attack_len - decay_len - release_len
    if sustain_len < 0:
        return numpy.linspace(1.0, 0.0, num_samples, dtype=numpy.float32)
    env = numpy.concatenate([
        numpy.linspace(0.0, 1.0, attack_len, dtype=numpy.float32),
        numpy.linspace(1.0, sustain, decay_len, dtype=numpy.float32),
        numpy.full(sustain_len, sustain, dtype=numpy.float32),
        numpy.linspace(sustain, 0.0, release_len, dtype=numpy.float32)
    ])
    return env.astype(numpy.float32)

def _add_reverb(buffer, sample_rate, delay_ms=50, decay=0.3):
    delay_samples = int(sample_rate * delay_ms / 1000.0)
    if delay_samples <= 0 or len(buffer) < delay_samples:
        return buffer
    output = numpy.copy(buffer)
    for i in range(delay_samples, len(buffer)):
        output[i] += decay * output[i - delay_samples]
    peak = numpy.max(numpy.abs(output))
    if peak > 0:
        output *= 0.8 / peak
    return output

def _pan_sound(audio_data, pan_position):
    left_gain = numpy.sqrt(0.5 * (1.0 - pan_position))
    right_gain = numpy.sqrt(0.5 * (1.0 + pan_position))
    stereo_data = numpy.column_stack([
        audio_data * left_gain,
        audio_data * right_gain
    ])
    return stereo_data.astype(numpy.int16)

def generate_track(params):
    sample_rate = params['sample_rate']
    tempo = params['tempo']
    key_shift = params['key_shift']
    bass_line = params['bass_line']
    rhythm_guitar = params['rhythm_guitar']
    solo_part = params['solo_part']
    accompaniment_part = params['accompaniment_part']
    drum_pattern = params['drum_pattern']
    loop_factor = params['loop_factor']
    drums_enabled = params['drums_enabled']
    solo_enabled = params['solo_enabled']
    accompaniment_enabled = params['accompaniment_enabled']

    max_beat = 0.0
    for part in (bass_line, rhythm_guitar, solo_part, accompaniment_part):
        for _, start, dur in part:
            end = start + dur
            if end > max_beat: max_beat = end
    for drum in drum_pattern:
        beat = drum[1] if len(drum) > 1 else 0
        if beat > max_beat: max_beat = beat
    total_beats = max_beat if max_beat > 0 else 16.0

    beat_dur = 60.0 / tempo
    total_dur = total_beats * beat_dur
    num_samples = int(sample_rate * total_dur)
    samples = [0.0] * num_samples

    def mix_in(start_beat, dur_beats, freq, wave_type='sine', amplitude=0.3):
        start_sec = start_beat * beat_dur
        dur_sec = dur_beats * beat_dur
        start_idx = int(start_sec * sample_rate)
        num = int(dur_sec * sample_rate)
        end_idx = min(start_idx + num, num_samples)
        if num <= 0:
            return
        t = numpy.linspace(0, dur_sec, num, endpoint=False, dtype=numpy.float32)
        if wave_type == 'sine':
            wave = numpy.sin(2 * numpy.pi * freq * t)
        elif wave_type == 'square':
            wave = numpy.sign(numpy.sin(2 * numpy.pi * freq * t))
        elif wave_type == 'sawtooth':
            wave = 2.0 * (t * freq - numpy.floor(0.5 + t * freq))
        else:
            wave = numpy.zeros(num, dtype=numpy.float32)
        env = _adsr_envelope(num)
        wave = wave * env * amplitude
        for i in range(num):
            idx = start_idx + i
            if idx < len(samples):
                samples[idx] += wave[i]

    def add_drum(drum_type, beat, amp=0.25):
        start_sec = beat * beat_dur
        idx = int(start_sec * sample_rate)
        if drum_type == 'kick':
            dur_samples = int(0.1 * sample_rate)
            for i in range(dur_samples):
                pos = idx + i
                if pos < num_samples:
                    t = i / sample_rate
                    freq = 150 * (1.0 - t * 5)
                    samples[pos] += amp * math.sin(2 * math.pi * freq * t) * (1.0 - t * 10)
        elif drum_type == 'snare':
            dur_samples = int(0.08 * sample_rate)
            for i in range(dur_samples):
                pos = idx + i
                if pos < num_samples:
                    t = i / sample_rate
                    samples[pos] += amp * (random.random() * 2 - 1) * (1.0 - t * 12)
        elif drum_type == 'hihat':
            dur_samples = int(0.04 * sample_rate)
            for i in range(dur_samples):
                pos = idx + i
                if pos < num_samples:
                    t = i / sample_rate
                    samples[pos] += amp * 0.3 * (random.random() * 2 - 1) * (1.0 - t * 25)

    def transposed(note):
        return note + key_shift

    if bass_line:
        for note, start_beat, dur_beats in bass_line:
            freq = midi_to_freq(transposed(note))
            mix_in(start_beat, dur_beats, freq, 'sine', amplitude=0.25)
    if rhythm_guitar:
        for note, start_beat, dur_beats in rhythm_guitar:
            root_freq = midi_to_freq(transposed(note))
            fifth = midi_to_freq(transposed(note + 7))
            mix_in(start_beat, dur_beats, root_freq, 'square', amplitude=0.15)
            mix_in(start_beat, dur_beats, fifth, 'square', amplitude=0.15)
    if solo_enabled and solo_part:
        for note, start_beat, dur_beats in solo_part:
            freq = midi_to_freq(transposed(note))
            mix_in(start_beat, dur_beats, freq, 'sine', amplitude=0.35)
    if accompaniment_enabled and accompaniment_part:
        for note, start_beat, dur_beats in accompaniment_part:
            freq = midi_to_freq(transposed(note))
            mix_in(start_beat, dur_beats, freq, 'sine', amplitude=0.2)
    if drums_enabled:
        for drum_type, beat in drum_pattern:
            add_drum(drum_type, beat)

    buf = numpy.array(samples, dtype=numpy.float32)
    buf = _add_reverb(buf, sample_rate, delay_ms=60, decay=0.25)
    if loop_factor > 1.0:
        tail = numpy.copy(buf)
        tail = _add_reverb(tail, sample_rate, delay_ms=200, decay=0.5)
        fade_out = numpy.linspace(1.0, 0.0, len(tail), dtype=numpy.float32)
        tail = tail * fade_out
        crossfade_len = int(0.01 * sample_rate)
        if crossfade_len > 0 and len(buf) >= crossfade_len and len(tail) >= crossfade_len:
            fade_out_cross = numpy.linspace(1.0, 0.0, crossfade_len, dtype=numpy.float32)
            fade_in_cross = numpy.linspace(0.0, 1.0, crossfade_len, dtype=numpy.float32)
            buf[-crossfade_len:] = buf[-crossfade_len:] * fade_out_cross + tail[:crossfade_len] * fade_in_cross
            tail = tail[crossfade_len:]
        buf = numpy.concatenate([buf, tail])
        total_dur *= 2
    if loop_factor > 2.0:
        left = numpy.copy(buf)
        right = numpy.copy(buf)
        stereo = _pan_sound(left, -1.0)
        right_stereo = _pan_sound(right, 1.0)
        third = (stereo.astype(numpy.float32) + right_stereo.astype(numpy.float32)).sum(axis=1) / 32768.0
        fade_in = numpy.linspace(0.0, 1.0, len(third), dtype=numpy.float32)
        third *= fade_in
        third = _add_reverb(third, sample_rate, delay_ms=100, decay=0.4)
        crossfade = int(0.01 * sample_rate)
        if crossfade > 0:
            fade_out_cross = numpy.linspace(1.0, 0.0, crossfade, dtype=numpy.float32)
            fade_in_cross = numpy.linspace(0.0, 1.0, crossfade, dtype=numpy.float32)
            buf[-crossfade:] = buf[-crossfade:] * fade_out_cross + third[:crossfade] * fade_in_cross
            third = third[crossfade:]
        buf = numpy.concatenate([buf, third])
        total_dur *= 1.5

    peak = numpy.max(numpy.abs(buf))
    if peak > 1.0:
        buf *= 0.95 / peak
    fade_samples = int(0.01 * sample_rate)
    if len(buf) > 2 * fade_samples:
        fade_out = numpy.linspace(1.0, 0.0, fade_samples, dtype=numpy.float32)
        buf[-fade_samples:] *= fade_out
        fade_in = numpy.linspace(0.0, 1.0, fade_samples, dtype=numpy.float32)
        buf[:fade_samples] *= fade_in
    return buf, total_beats


_executor = None
def _get_executor():
    global _executor
    if _executor is None:
        _executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)
    return _executor


class Music:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.audio = Audio()
        self._tempo = 120
        self._key_shift = 0
        self._volume = 0.5
        self.drums_enabled = True
        self.solo_enabled = False
        self.accompaniment_enabled = False
        self.bass_line = []
        self.rhythm_guitar = []
        self.solo_part = []
        self.accompaniment_part = []
        self.drum_pattern = []
        self._buffer = None
        self._buffer_duration = 0
        self._playing = False
        self._thread = None
        self._loop_mode = True
        self._loop_finished_event = threading.Event()
        self._loop_factor = 1.0
        self.chords = []
        self._future = None
        self.generate_notes()
        self._submit_async_generation()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = max(0.0, min(1.0, value))

    @property
    def is_playing(self):
        return self.audio.is_playing()

    def play(self):
        self._playing = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._stream, daemon=True)
            self._thread.start()

    def pause(self):
        self._playing = False

    def stop(self):
        self._playing = False

    def play_one(self):
        self._loop_mode = False
        self._loop_finished_event.clear()
        self.play()

    def _submit_async_generation(self):
        params = {
            'sample_rate': self.sample_rate,
            'tempo': self._tempo,
            'key_shift': self._key_shift,
            'bass_line': self.bass_line,
            'rhythm_guitar': self.rhythm_guitar,
            'solo_part': self.solo_part,
            'accompaniment_part': self.accompaniment_part,
            'drum_pattern': self.drum_pattern,
            'loop_factor': self._loop_factor,
            'drums_enabled': self.drums_enabled,
            'solo_enabled': self.solo_enabled,
            'accompaniment_enabled': self.accompaniment_enabled
        }
        self._future = _get_executor().submit(generate_track, params)

    def _wait_for_buffer(self):
        if self._future and self._buffer is None:
            buf, beats = self._future.result()
            self._buffer = buf
            self._total_beats = beats
            self._buffer_duration = beats * 60.0 / self._tempo

    def _get_full_buffer(self):
        self._wait_for_buffer()
        return self._buffer, self._buffer_duration

    def _generate_chunk(self, start_beat, chunk_beats):
        full_buf, full_dur = self._get_full_buffer()
        total_beats = (self._buffer_duration * self._tempo) / 60.0
        beat_dur = 60.0 / self._tempo
        total_samples = len(full_buf)
        start_sample = int(start_beat * beat_dur * self.sample_rate)
        end_sample = start_sample + int(chunk_beats * beat_dur * self.sample_rate)
        if end_sample > total_samples:
            first = full_buf[start_sample:total_samples]
            second = full_buf[0:end_sample - total_samples]
            return numpy.concatenate((first, second))
        return full_buf[start_sample:end_sample]

    def _stream(self):
        self._wait_for_buffer()
        self.audio.stream_start(self.sample_rate)
        chunk_dur = 0.5
        chunk_beats = (self._tempo / 60.0) * chunk_dur
        total_beats = (self._buffer_duration * self._tempo) / 60.0
        beat_pos = 0.0
        loop_done = False
        try:
            while self._playing and not loop_done:
                t0 = time.monotonic()
                chunk = self._generate_chunk(beat_pos, chunk_beats)
                pcm = (chunk * 32767).astype(numpy.int16).tobytes()
                self.audio.stream_write(pcm)
                beat_pos += chunk_beats
                if beat_pos >= total_beats:
                    beat_pos -= total_beats
                    if not self._loop_mode:
                        loop_done = True
                elapsed = time.monotonic() - t0
                sleep_time = chunk_dur - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except Exception as err:
            logging.error(f"Music streaming error: {err}")
        finally:
            self.audio.stream_stop()
        self._loop_finished_event.set()
        self._playing = False

    def mutation(self, track_name=None, **kwargs):
        mutation_map = {
            "speed_up": lambda: setattr(self, '_tempo', self._tempo * 1.1),
            "speed_down": lambda: setattr(self, '_tempo', self._tempo / 1.1),
            "key_up": lambda: setattr(self, '_key_shift', self._key_shift + 1),
            "key_down": lambda: setattr(self, '_key_shift', self._key_shift - 1),
            "drums_on": lambda: setattr(self, 'drums_enabled', True),
            "drums_off": lambda: setattr(self, 'drums_enabled', False),
            "solo_on": lambda: setattr(self, 'solo_enabled', True),
            "solo_off": lambda: setattr(self, 'solo_enabled', False),
            "acc_on": lambda: setattr(self, 'accompaniment_enabled', True),
            "acc_off": lambda: setattr(self, 'accompaniment_enabled', False),
        }
        if track_name in mutation_map:
            mutation_map[track_name]()
        for attr, val in kwargs.items():
            if hasattr(self, attr):
                setattr(self, attr, val)
        self._buffer = None
        was_playing = self._playing
        if was_playing:
            self.stop()
        self.generate_notes()
        self._submit_async_generation()
        if was_playing:
            self.play()

    def generate_notes(self):
        self.bass_line.clear()
        self.rhythm_guitar.clear()
        self.solo_part.clear()
        self.accompaniment_part.clear()
        self.drum_pattern.clear()
