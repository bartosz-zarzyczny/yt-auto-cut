import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import desktop_app
import ipsc_automato


class VideoTextTests(unittest.TestCase):
    def test_video_texts_and_results_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            music = root / "music"
            source.mkdir()
            music.mkdir()
            (source / "video.mp4").touch()
            results = {"miejsce": 1, "procent": "100%", "czas": 10, "hf": 1, "punkty": 10}

            for add_results in (False, True):
                for add_texts in (False, True):
                    with self.subTest(add_results=add_results, add_texts=add_texts):
                        config = ipsc_automato.KonfiguracjaSciezek(
                            folder_wejsciowy=source,
                            folder_wyjsciowy=root / "output",
                            folder_muzyki=music,
                            plik_z_wynikami=root / "results.txt",
                            plik_z_tekstami=root / "texts.txt",
                            dodaj_napisy=add_results,
                            add_video_texts=add_texts,
                        )
                        video = MagicMock()
                        video.duration = 20
                        video.resize.return_value = video
                        result_clip = MagicMock()
                        result_clip.set_position.return_value = sentinel.result
                        with patch.object(ipsc_automato, "check_environment", return_value=(True, "codec")), \
                             patch.object(ipsc_automato, "czytaj_wyniki_z_pliku", return_value={1: results}), \
                             patch.object(ipsc_automato, "assign_tracks", return_value=[("video.mp4", 1, (100, 100))]), \
                             patch.object(ipsc_automato, "zglos_wykrycie_timera", return_value=[]), \
                             patch.object(ipsc_automato, "VideoFileClip", return_value=video), \
                             patch.object(ipsc_automato, "trim_video", return_value=video), \
                             patch.object(ipsc_automato, "text_clip", return_value=result_clip), \
                             patch.object(ipsc_automato, "choose_font"), \
                             patch.object(ipsc_automato, "create_text_clips", return_value=[sentinel.text]) as texts, \
                             patch.object(ipsc_automato, "create_logo_clip", return_value=None), \
                             patch.object(ipsc_automato, "CompositeVideoClip") as composite, \
                             patch.object(ipsc_automato, "CancellableProgressLogger"), \
                             patch.object(ipsc_automato.os, "replace"), \
                             patch.object(ipsc_automato, "generate_title", return_value="title"):
                            self.assertTrue(ipsc_automato.uruchom_automatyzacje(konfiguracja=config))
                            layers = [video]
                            if add_results:
                                layers.append(sentinel.result)
                            if add_texts:
                                layers.append(sentinel.text)
                                texts.assert_called_once_with(str(config.plik_z_tekstami), 20, unittest.mock.ANY)
                            else:
                                texts.assert_not_called()
                            composite.assert_called_once_with(layers, size=(100, 100))

    def test_checkbox_state_is_saved_and_passed_to_config(self):
        app = QApplication.instance() or QApplication([])
        values = {}
        settings = MagicMock()
        settings.value.side_effect = lambda key, default=None: values.get(key, default)
        settings.setValue.side_effect = lambda key, value: values.__setitem__(key, value)
        with patch.object(desktop_app, "QSettings", return_value=settings), \
             patch.object(desktop_app.MainWindow, "_load_startup_files"):
            window = desktop_app.MainWindow()
            self.assertTrue(window.video_texts_check.isChecked())
            self.assertEqual(window.subtitles_check.text(), "Czy dodać wyniki")
            window.subtitles_check.setChecked(False)
            self.assertTrue(window._get_config().add_video_texts)
            window.video_texts_check.setChecked(False)
            self.assertFalse(window._get_config().add_video_texts)
            self.assertEqual(values["add_video_texts"], "false")
            window.subtitles_check.setChecked(True)
            self.assertTrue(window._get_config().dodaj_napisy)
            self.assertFalse(window._get_config().add_video_texts)
            window.close()

            restored = desktop_app.MainWindow()
            self.assertFalse(restored.video_texts_check.isChecked())
            restored.close()
        self.assertIsNotNone(app)

    def test_missing_text_file_is_required_only_when_enabled(self):
        app = QApplication.instance() or QApplication([])
        settings = MagicMock()
        settings.value.side_effect = lambda key, default=None: default
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(desktop_app, "QSettings", return_value=settings), \
             patch.object(desktop_app.MainWindow, "_load_startup_files"), \
             patch.object(desktop_app.QMessageBox, "warning") as warning:
            root = Path(directory)
            window = desktop_app.MainWindow()
            for key in ("folder_wejsciowy", "folder_wyjsciowy", "folder_muzyki"):
                window.fields[key].setText(str(root))
            for key in ("plik_z_torami", "plik_opisu_zawodow"):
                path = root / (key + ".txt")
                path.touch()
                window.fields[key].setText(str(path))
            window.fields["plik_z_tekstami"].setText(str(root / "missing.txt"))

            window._start()
            # Błąd jest pokazywany pod polem, bez okienka.
            warning.assert_not_called()
            self.assertIn("plik nie istnieje", window._path_errors["plik_z_tekstami"].text())
            self.assertFalse(window._path_errors["plik_z_tekstami"].isHidden())
            self.assertTrue(window.fields["plik_z_tekstami"].property("error"))
            window.video_texts_check.setChecked(False)
            window._start()
            self.assertIn("nie ma filmów", window._path_errors["folder_wejsciowy"].text())
            self.assertFalse(window._path_errors["folder_wejsciowy"].isHidden())
            window.close()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
