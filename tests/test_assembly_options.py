import io
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

import automato
import fast_trim
import ipsc_automato
from timer_detect import energy_near_peak
from timer_trim import choose_trim_range

DESCRIPTION = "Nazwa zawodów: Liga testowa\nData zawodów: 2026-11-21\nMiejsce: Strzelnica\n"


def _loop_energy_near_peak(energy, peaks):
    """Poprzednia (pętlowa) implementacja — wzorzec dla wersji wektorowej."""
    result = np.zeros(energy.shape[1])
    for i in range(energy.shape[1]):
        lo, hi = max(peaks[i] - 2, 0), peaks[i] + 3
        result[i] = energy[lo:hi, i].sum()
    return result


def _project(root: Path, results: str = "1;10.0\n", videos=("a.mp4", "b.mp4")):
    source = root / "source"
    source.mkdir()
    for name in videos:
        (source / name).write_bytes(b"")
    (root / "results.txt").write_text(results, encoding="utf-8")
    (root / "opis.txt").write_text(DESCRIPTION, encoding="utf-8")
    (root / "output").mkdir()
    return dict(
        folder_wejsciowy=source,
        folder_wyjsciowy=root / "output",
        folder_muzyki=root / "music",
        plik_z_wynikami=root / "results.txt",
        plik_z_torami=root / "missing_tracks.txt",
        plik_opisu_zawodow=root / "opis.txt",
        tryb_wynikow=ipsc_automato.TRYB_WYNIKOW_TRENING,
    )


class TimerTests(unittest.TestCase):
    def test_vectorized_energy_matches_loop(self):
        rng = np.random.default_rng(1)
        energy = rng.random((40, 300))
        peaks = rng.integers(0, 40, 300)
        peaks[:3] = [0, 1, 39]  # krawędzie pasma
        np.testing.assert_allclose(energy_near_peak(energy, peaks), _loop_energy_near_peak(energy, peaks))

    def test_trim_range_requires_time_and_single_signal(self):
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(choose_trim_range([(2.0, 2800)], None, 30))
            self.assertIsNone(choose_trim_range([], 10.0, 30))
            self.assertEqual(choose_trim_range([(2.0, 2800)], 10.0, 30), (1.5, 12.8))


class FastTrimTests(unittest.TestCase):
    def test_command_copies_video_and_trims(self):
        command = fast_trim.build_trim_command("ffmpeg", "in.mov", "out.mp4", (1.5, 12.8))
        self.assertIn("copy", command[command.index("-c:v") + 1])
        self.assertEqual(command[command.index("-ss") + 1], "1.500")
        self.assertEqual(command[command.index("-to") + 1], "12.800")
        self.assertEqual(command[-1], "out.mp4")

    def test_command_without_range_keeps_whole_file(self):
        command = fast_trim.build_trim_command("ffmpeg", "in.mov", "out.mp4", None)
        self.assertNotIn("-ss", command)


class PlanTests(unittest.TestCase):
    def test_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _project(root)
            config = ipsc_automato.KonfiguracjaSciezek(**paths, dodaj_napisy=True)
            plan = ipsc_automato.plan_assembly(config)
            self.assertEqual([item.action for item in plan], ["render", "skip_no_result"])
            self.assertEqual(plan[0].output_name, "2026-11-21 - Liga testowa - Tor 1 #bodycam.mp4")

            trim = ipsc_automato.plan_assembly(
                ipsc_automato.KonfiguracjaSciezek(**paths, dodaj_napisy=True, trim_only=True)
            )
            self.assertEqual([item.action for item in trim], ["render", "render"])

            (root / "output" / plan[0].output_name).write_bytes(b"")
            self.assertEqual(ipsc_automato.plan_assembly(config)[0].action, "skip_exists")
            overwrite = ipsc_automato.KonfiguracjaSciezek(**paths, dodaj_napisy=True, overwrite_existing=True)
            self.assertEqual(ipsc_automato.plan_assembly(overwrite)[0].action, "render")

    def test_missing_description_keeps_technical_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _project(root)
            (root / "opis.txt").unlink()
            messages = []
            plan = ipsc_automato.plan_assembly(ipsc_automato.KonfiguracjaSciezek(**paths), messages.append)
            self.assertEqual(plan[0].output_name, "Gotowe_Stage_1.mp4")
            self.assertTrue(any("nazwy techniczne" in message for message in messages))


class CliTests(unittest.TestCase):
    def test_render_flags_build_config(self):
        args = automato.build_parser().parse_args(
            ["render", "--trim-only", "--no-music", "--no-results", "--overwrite", "--orientation", "H",
             "--results-mode", "ecm", "--input", "x"]
        )
        config = automato.build_config(args)
        self.assertTrue(config.trim_only)
        self.assertFalse(config.add_music)
        self.assertFalse(config.dodaj_napisy)
        self.assertTrue(config.overwrite_existing)
        self.assertEqual(config.domyslna_orientacja, "H")
        self.assertEqual(config.tryb_wynikow, "ecm")
        self.assertEqual(config.folder_wejsciowy, Path("x"))

    def test_render_exit_codes(self):
        with patch.object(ipsc_automato, "uruchom_automatyzacje", return_value=True), \
             patch.object(automato.signal, "signal"):
            self.assertEqual(automato.main(["render"]), automato.EXIT_OK)
        with patch.object(ipsc_automato, "uruchom_automatyzacje", return_value=False), \
             patch.object(automato.signal, "signal"):
            self.assertEqual(automato.main(["render"]), automato.EXIT_ERRORS)

    def test_publish_youtube_defaults_to_preview(self):
        with patch("youtube_upload.main") as youtube_main:
            automato.main(["publish", "youtube"])
        self.assertNotIn("--publish", youtube_main.call_args.args[0])


@unittest.skipUnless(shutil.which("ffmpeg") or os.environ.get("IMAGEIO_FFMPEG_EXE"), "brak FFmpeg")
class TrimOnlyEndToEndTests(unittest.TestCase):
    def test_trim_only_produces_trimmed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _project(root, results="1;2.0\n", videos=())
            video = paths["folder_wejsciowy"] / "run.mp4"
            # 8 s obrazu, cisza z sygnałem 2800 Hz (timer) od 2,0 do 2,6 s
            subprocess.run(
                [fast_trim.ffmpeg_binary(), "-v", "error", "-y",
                 "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=8",
                 "-f", "lavfi", "-i", "sine=frequency=2800:sample_rate=44100:duration=8",
                 "-filter_complex", "[1:a]volume='if(between(t,2,2.6),1,0)':eval=frame[a]",
                 "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-g", "15", "-c:a", "aac", str(video)],
                check=True,
            )
            config = ipsc_automato.KonfiguracjaSciezek(**paths, trim_only=True)
            with redirect_stdout(io.StringIO()):
                self.assertTrue(ipsc_automato.uruchom_automatyzacje(konfiguracja=config))
            output = paths["folder_wyjsciowy"] / "2026-11-21 - Liga testowa - Tor 1 #bodycam.mp4"
            self.assertTrue(output.is_file())
            duration = fast_trim.probe_duration(output)
            self.assertLess(duration, 5.0)   # oczekiwane ok. 3,3 s (1,5 → 4,8)
            self.assertGreater(duration, 2.5)
            self.assertEqual(list(paths["folder_wyjsciowy"].glob("*TEMP_MPY*")), [])


if __name__ == "__main__":
    unittest.main()
