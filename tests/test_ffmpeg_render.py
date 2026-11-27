import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PIL import Image

import ffmpeg_render
import ipsc_automato
from fast_trim import ffmpeg_binary, probe_media
from ffmpeg_render import POSITION_CENTER, Overlay, RenderJob, build_command
from video_cancellation import GenerationCancelled


def _job(**changes):
    values = dict(source=Path("in.mp4"), output=Path("out.mp4"), resolution=(1080, 1920), duration=12.5,
                  trim_start=1.5, overlays=(), codec="libx264")
    values.update(changes)
    return RenderJob(**values)


class BuildCommandTests(unittest.TestCase):
    def test_trim_scale_and_quality(self):
        command = build_command("ffmpeg", _job(), [])
        self.assertEqual(command[command.index("-ss") + 1], "1.500")
        self.assertEqual(command[command.index("-t") + 1], "12.500")
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("scale=1080:1920", graph)
        self.assertIn("-crf", command)
        self.assertEqual(command[command.index("-map") + 1], "[vout]")
        self.assertIn("0:a:0", command)

    def test_overlays_with_fade_and_center(self):
        image = Image.new("RGBA", (10, 10))
        overlays = [Overlay(image, POSITION_CENTER, 1632, 0, 12.5),
                    Overlay(image, 860, 20, 2.0, 9.8, fade=True)]
        graph = build_command("ffmpeg", _job(overlays=overlays), [Path("a.png"), Path("b.png")])
        graph = graph[graph.index("-filter_complex") + 1]
        self.assertIn("overlay=x=(main_w-overlay_w)/2:y=1632", graph)
        self.assertIn("fade=t=in:st=2.000:d=0.4:alpha=1", graph)
        self.assertIn("fade=t=out:st=9.400", graph)
        self.assertIn("between(t,2.000,9.800)", graph)

    def test_music_mixed_or_alone(self):
        with_audio = build_command("ffmpeg", _job(music=Path("m.mp3")), [])
        graph = with_audio[with_audio.index("-filter_complex") + 1]
        self.assertIn("amix=inputs=2", graph)
        self.assertIn("volume=0.12", graph)
        self.assertIn("afade=t=out:st=11.500", graph)
        self.assertIn("-stream_loop", with_audio)
        silent = build_command("ffmpeg", _job(music=Path("m.mp3"), has_audio=False), [])
        self.assertNotIn("amix", silent[silent.index("-filter_complex") + 1])
        no_audio = build_command("ffmpeg", _job(has_audio=False), [])
        self.assertNotIn("-c:a", no_audio)

    def test_codec_quality(self):
        self.assertIn("-cq", ffmpeg_render.quality_args("h264_nvenc"))
        self.assertIn("-q:v", ffmpeg_render.quality_args("h264_videotoolbox"))
        self.assertEqual(ffmpeg_render.quality_args("unknown"), ["-b:v", "8000k"])

    def test_progress_line(self):
        self.assertEqual(ffmpeg_render._progress_seconds("out_time_us=2500000"), 2.5)
        self.assertIsNone(ffmpeg_render._progress_seconds("frame=12"))
        self.assertEqual(ffmpeg_render._progress_seconds("out_time_ms=-5"), 0)


class RenderEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "src.mp4"
        self.music = self.root / "music.wav"
        ffmpeg = ffmpeg_binary()
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-c:a", "aac",
                        "-shortest", str(self.source)], check=True)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
                        str(self.music)], check=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_render_with_overlay_music_and_progress(self):
        output = self.root / "out.mp4"
        plate = Image.new("RGBA", (100, 20), (255, 255, 255, 255))
        progress = []
        job = RenderJob(self.source, output, (180, 320), 3.0, trim_start=1.0, has_audio=True, music=self.music,
                        overlays=[Overlay(plate, POSITION_CENTER, 270, 0.0, 3.0),
                                  Overlay(plate, 10, 10, 0.5, 2.5, fade=True)])
        ffmpeg_render.run(ffmpeg_binary(), job, Event(), progress.append)
        info = probe_media(output)
        self.assertAlmostEqual(info["duration"], 3.0, delta=0.15)
        self.assertTrue(info["has_audio"])
        self.assertEqual(progress[-1], 1.0)
        frame = self.root / "frame.png"
        subprocess.run([ffmpeg_binary(), "-v", "error", "-y", "-ss", "1.5", "-i", str(output), "-frames:v", "1",
                        str(frame)], check=True)
        with Image.open(frame) as image:
            self.assertEqual(image.size, (180, 320))
            self.assertEqual(image.convert("RGB").getpixel((90, 280)), (255, 255, 255))

    def test_cancel_stops_render(self):
        cancel = Event()
        cancel.set()
        job = RenderJob(self.source, self.root / "x.mp4", (180, 320), 5.0)
        with self.assertRaises(GenerationCancelled):
            ffmpeg_render.run(ffmpeg_binary(), job, cancel)

    def test_timer_from_plan_is_not_detected_again(self):
        source_dir = self.root / "videos"
        source_dir.mkdir()
        self.source.rename(source_dir / "run.mp4")
        (self.root / "results.txt").write_text("1;2\n", encoding="utf-8")
        config = ipsc_automato.KonfiguracjaSciezek(
            folder_wejsciowy=source_dir, folder_wyjsciowy=self.root / "out", folder_muzyki=self.root / "none",
            plik_z_wynikami=self.root / "results.txt", plik_z_torami=self.root / "none.txt",
            plik_opisu_zawodow=self.root / "none.txt", tryb_wynikow="trening", dodaj_napisy=True,
            add_video_texts=False, domyslna_orientacja="H",
        )
        with patch.object(ipsc_automato, "zglos_wykrycie_timera") as detect, \
             patch.object(ipsc_automato, "check_environment", return_value=(True, "libx264")), \
             redirect_stdout(io.StringIO()):
            self.assertTrue(ipsc_automato.uruchom_automatyzacje(konfiguracja=config, timer_starts={"run.mp4": 1.0}))
        detect.assert_not_called()
        output = self.root / "out" / "Gotowe_Stage_1.mp4"
        # start 1,0 s − 0,5 s zapasu, czas 2 s + 0,5 s + 0,8 s = 3,3 s
        self.assertAlmostEqual(probe_media(output)["duration"], 3.3, delta=0.15)


if __name__ == "__main__":
    unittest.main()
