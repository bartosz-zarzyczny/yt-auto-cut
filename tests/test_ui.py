import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import desktop_app
import ui_theme


def _window(values=None):
    values = {} if values is None else values
    settings = MagicMock()
    settings.value.side_effect = lambda key, default=None: values.get(key, default)
    settings.setValue.side_effect = lambda key, value: values.__setitem__(key, value)
    with patch.object(desktop_app, "QSettings", return_value=settings), \
         patch.object(desktop_app.MainWindow, "_load_startup_files"):
        return desktop_app.MainWindow()


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stylesheets_have_no_placeholders_left(self):
        for palette in (ui_theme.LIGHT, ui_theme.DARK):
            sheet = ui_theme.build_stylesheet(palette, "Mono")
            self.assertNotIn("$", sheet)
        self.assertEqual(set(ui_theme.LIGHT), set(ui_theme.DARK))

    def test_theme_mode_is_saved_and_applied(self):
        values = {}
        window = _window(values)
        window._set_theme_mode(ui_theme.THEME_LIGHT)
        self.assertEqual(values["theme"], ui_theme.THEME_LIGHT)
        self.assertIn(ui_theme.LIGHT["bg"], self.app.styleSheet())
        window._set_theme_mode(ui_theme.THEME_DARK)
        self.assertIn(ui_theme.DARK["bg"], self.app.styleSheet())
        window.close()


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_log_is_hidden_by_default_and_toggle_is_remembered(self):
        values = {}
        window = _window(values)
        self.assertTrue(window.log_group.isHidden())
        window.log_toggle.setChecked(True)
        self.assertFalse(window.log_group.isHidden())
        self.assertEqual(values["log_visible"], "true")
        window.close()

    def test_editor_autosaves(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "teksty.txt"
            window = _window()
            window.fields["plik_z_tekstami"].setText(str(path))
            window.editors["plik_z_tekstami"].setPlainText("[Nowy tekst]")
            self.assertTrue(window._autosave_timers["plik_z_tekstami"].isActive())
            self.assertTrue(window._autosave("plik_z_tekstami"))
            self.assertEqual(path.read_text(encoding="utf-8"), "[Nowy tekst]")
            self.assertNotIn("plik_z_tekstami", window._dirty_editors)
            window.close()

    def test_render_progress_moves_overall_bar(self):
        window = _window()
        window._update_progress(2, 4, "b.mp4", "started")
        self.assertEqual(window.progress_bar.value(), desktop_app.PROGRESS_STEPS // 4)
        window._update_render_progress(0.5)
        self.assertEqual(window.progress_bar.value(), int(1.5 / 4 * desktop_app.PROGRESS_STEPS))
        self.assertIn("50%", window.status_detail.text())
        window.close()

    def test_api_keys_are_saved_to_settings_file(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.json"
            stored = {}
            with patch.object(desktop_app, "load_settings", side_effect=lambda: dict(stored)), \
                 patch.object(desktop_app, "save_settings", side_effect=lambda data: stored.update(data)):
                window = _window()
                window.api_fields[desktop_app.KEY_BUFFER_API].setText("token-123")
                window._save_api_keys()
            self.assertEqual(stored[desktop_app.KEY_BUFFER_API], "token-123")
            self.assertFalse(settings_file.exists())
            window.close()


class FormatTests(unittest.TestCase):
    def test_duration_format(self):
        self.assertEqual(desktop_app.format_duration(42), "42 s")
        self.assertEqual(desktop_app.format_duration(80), "1 min 20 s")
        self.assertEqual(desktop_app.format_duration(3720), "1 h 02 min")


if __name__ == "__main__":
    unittest.main()
