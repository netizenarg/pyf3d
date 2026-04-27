import platform
import struct
import subprocess
import tempfile
import os
import threading
import time
import logging

try:
    from generator import Generator
except:
    from .generator import Generator


class Audio:

    def __init__(self):
        self.system = platform.system()

        self.WinPlaySound = None
        self.WinPlaySoundFlags = 0
        self.MacNSSound = None
        self.MacNSData = None

        match self.system:
            case 'Windows':
                try:
                    from winsound import PlaySound, SND_MEMORY, SND_ASYNC, SND_FILENAME
                except Exception as err:
                    logging.error(f'{err}')
                else:
                    self.WinPlaySound = PlaySound
                    self.WinPlaySoundFlags = SND_MEMORY | SND_ASYNC
                    self.WinPlaySoundFilename = SND_FILENAME | SND_ASYNC
            case 'Darwin':
                try:
                    from AppKit import NSSound
                    from Foundation import NSData
                except Exception as err:
                    logging.error(f'{err}')
                else:
                    self.MacNSSound = NSSound
                    self.MacNSData = NSData

        self.generator = Generator()

        self._stream_proc = None
        self._stream_sample_rate = None
        self._stream_buffer = bytearray()
        self._stream_buffer_lock = threading.Lock()

    def _samples_to_wav_bytes(self, samples, sample_rate, volume):
        pcm_data = []
        for s in samples:
            s = max(-1.0, min(1.0, s))
            pcm_value = int(s * 32767)
            pcm_value = max(-32768, min(32767, pcm_value))
            pcm_data.append(struct.pack('<h', pcm_value))
        pcm_bytes = b''.join(pcm_data)
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_bytes)
        header = struct.pack('<4sI4s4sIHHIIHH',
            b'RIFF', 36 + data_size, b'WAVE', b'fmt ',
            16, 1, num_channels, sample_rate, byte_rate,
            block_align, bits_per_sample, b'data', data_size)
        return header + pcm_bytes

    def _pcm_to_samples(self, pcm_bytes):
        """Convert 16-bit LE PCM bytes to list of floats in [-1,1]."""
        count = len(pcm_bytes) // 2
        samples = []
        for i in range(count):
            val = struct.unpack('<h', pcm_bytes[i*2:(i+1)*2])[0]
            samples.append(val / 32768.0)
        return samples

    def play(self, samples, sample_rate=44100, volume=0.5):
        if volume != 1.0:
            samples = [s * volume for s in samples]
        match self.system:
            case 'Windows':
                wav_bytes = self._samples_to_wav_bytes(samples, sample_rate, volume=volume)#ATTENTION: NOT USE CONSTANT VOLUME
                self.WinPlaySound(wav_bytes, self.WinPlaySoundFlags)
            case 'Linux':
                pcm_bytes = b''
                for s in samples:
                    s = max(-1.0, min(1.0, s))
                    pcm_value = int(s * 32767)
                    pcm_value = max(-32768, min(32767, pcm_value))
                    pcm_bytes += struct.pack('<h', pcm_value)
                proc = subprocess.Popen(
                    ['aplay', '-f', 'S16_LE', '-r', str(sample_rate), '-c', '1', '-q', '--nonblock'],
                    stdin=subprocess.PIPE
                )
                proc.stdin.write(pcm_bytes)
                proc.stdin.close()
                proc.wait()
            case 'Darwin':
                wav_bytes = self._samples_to_wav_bytes(samples, sample_rate, volume=volume)#ATTENTION: NOT USE CONSTANT VOLUME
                if self.MacNSSound and self.MacNSData:
                    sound = self.MacNSSound.alloc().initWithData_(self.MacNSData.dataWithBytes_length_(wav_bytes, len(wav_bytes)))
                    if sound:
                        sound.play()
                    else:
                        logging.error("Failed to load sound data.")
                else:
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                        tmp_file.write(wav_bytes)
                        tmp_path = tmp_file.name
                    try:
                        subprocess.run(['afplay', tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    finally:
                        os.unlink(tmp_path)
            case _:
                logging.error(f"Unsupported operating system: {self.system}")

    def play_random(self, duration=2.0, volume=0.5, sample_rate=44100, mode='noise', **kwargs):
        samples = self.generator.generate_random(duration, volume, mode, **kwargs)
        self.play(samples, sample_rate=sample_rate, volume=1.0)

    def play_thread(self, samples, sample_rate=44100, volume=0.5, callback=None):
        def target():
            try:
                self.play(samples, sample_rate, volume)
            except Exception as e:
                logging.error(f"Playback error: {e}")
            if callback:
                callback()
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread

    def play_random_thread(self, duration=2.0, volume=0.5, sample_rate=44100,
                          mode='noise', callback=None, **kwargs):
        def target():
            samples = self.generator.generate_random(duration, volume, mode, **kwargs)
            self.play(samples, sample_rate, volume=1.0)
            if callback:
                callback()
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread

    def stream_start(self, sample_rate, volume=0.5):
        self.stream_stop()
        self._stream_sample_rate = sample_rate
        if self.system == 'Linux':
            subprocess.run(['amixer', 'set', 'PCM', f'{int(volume*100)}%'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._stream_proc = subprocess.Popen(
                ['aplay', '-f', 'S16_LE', '-c', '1', '-q', '-r', str(sample_rate)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            with self._stream_buffer_lock:
                self._stream_buffer.clear()

    def stream_write(self, pcm_bytes):
        if self.system == 'Linux':
            if self._stream_proc is None or self._stream_proc.poll() is not None:
                self.stream_start(self._stream_sample_rate or 44100)
            while True:
                try:
                    self._stream_proc.stdin.write(pcm_bytes)
                    self._stream_proc.stdin.flush()
                    break
                except BrokenPipeError:
                    self.stream_start(self._stream_sample_rate or 44100)
                except OSError as e:
                    if hasattr(e, 'errno') and e.errno == 4:
                        continue
                    raise
        else:
            with self._stream_buffer_lock:
                self._stream_buffer.extend(pcm_bytes)

    def stream_stop(self):
        if self.system == 'Linux':
            if self._stream_proc:
                try:
                    self._stream_proc.stdin.close()
                except:
                    pass
                self._stream_proc.terminate()
                try:
                    self._stream_proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self._stream_proc.kill()
                    self._stream_proc.wait()
                self._stream_proc = None
        else:
            with self._stream_buffer_lock:
                pcm = bytes(self._stream_buffer)
                self._stream_buffer.clear()
            if pcm:
                samples = self._pcm_to_samples(pcm)
                self.play(samples, sample_rate=self._stream_sample_rate or 44100, volume=1.0)
        self._stream_sample_rate = None

    def is_playing(self):
        if self.system == 'Linux':
            return self._stream_proc is not None and self._stream_proc.poll() is None
        # Non-Linux: we don't track one-shot plays started by stream_stop
        return False
