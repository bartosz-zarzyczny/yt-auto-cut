import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

import timer_detect as td

TONE_HZ = 2690


def _recording(segments, length=12.0, seed=0):
    """Syntetyczne nagranie: cisza przed startem, potem głośna część (strzały, ruch), która podnosi
    próg głośności — tak jak w prawdziwych nagraniach — oraz podane fragmenty (ton timera lub szum)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(length * td.SR)) / td.SR
    audio = 0.002 * rng.standard_normal(t.size)
    busy = int(5.0 * td.SR)
    audio[busy:] += 0.05 * rng.standard_normal(t.size - busy)
    for kind, start, end, level in segments:
        a, b = int(start * td.SR), int(end * td.SR)
        if kind == "tone":
            audio[a:b] += level * np.sin(2 * np.pi * TONE_HZ * t[a:b])
        else:  # krótki szerokopasmowy dźwięk (krok, szelest)
            audio[a:b] += level * rng.standard_normal(b - a)
    return audio


def _detect(audio):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audio.wav"
        wavfile.write(path, td.SR, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
        return td.znajdz_sygnaly_timera(str(path))


class TimerDetectionTests(unittest.TestCase):
    def test_clean_tone_is_detected(self):
        signals = _detect(_recording([("tone", 3.0, 3.45, 0.05)]))
        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0][0], 3.0, delta=0.05)
        self.assertAlmostEqual(signals[0][1], TONE_HZ, delta=30)

    def test_tone_interrupted_by_short_noise_is_one_signal(self):
        # Jak w VID_…226: ton 0,4 s, w połowie zagłuszony szerokopasmowym dźwiękiem (każda część < 0,26 s).
        audio = _recording([("tone", 3.0, 3.42, 0.05), ("noise", 3.2, 3.27, 0.25)])
        signals = _detect(audio)
        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0][0], 3.0, delta=0.05)

    def test_quieter_middle_of_tone_does_not_split_it(self):
        # Jak w VID_…229: środek tonu cichszy od progu głośności, ale wciąż czysty.
        audio = _recording([("tone", 3.0, 3.2, 0.05), ("tone", 3.2, 3.34, 0.005), ("tone", 3.34, 3.5, 0.08)])
        signals = _detect(audio)
        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0][0], 3.0, delta=0.05)

    def test_short_blip_is_ignored(self):
        self.assertEqual(_detect(_recording([("tone", 3.0, 3.1, 0.05)])), [])

    def test_only_noise_gives_no_signal(self):
        self.assertEqual(_detect(_recording([("noise", 3.0, 3.4, 0.3)])), [])


if __name__ == "__main__":
    unittest.main()
