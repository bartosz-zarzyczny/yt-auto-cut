import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import desktop_app
from generate_names import apply_match_fields, read_match_data
from results_parser import detect_results_mode
from ui.navigation import STATUS_OK, STATUS_WARNING
from ui.plan_table import TIMER_NOT_CHECKED, TIMER_NOT_FOUND, PlanRow, PlanTable, parse_track_order
from ui_icons import icon

PRACTISCORE_PASTE = "Stage 3  Tor 3  5  87.21%  60.0  76  6.1234  12.45\n"


def _window(values):
    settings = MagicMock()
    settings.value.side_effect = lambda key, default=None: values.get(key, default)
    settings.setValue.side_effect = lambda key, value: values.__setitem__(key, value)
    with patch.object(desktop_app, "QSettings", return_value=settings), \
         patch.object(desktop_app.MainWindow, "_load_startup_files"):
        return desktop_app.MainWindow()


def _project(root: Path) -> dict:
    source = root / "source"
    source.mkdir()
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        (source / name).write_bytes(b"")
    (root / "output").mkdir()
    (root / "results.txt").write_text("1;10,5\n2;12\n", encoding="utf-8")
    (root / "tracks.txt").write_text("1\n2\n3\n", encoding="utf-8")
    (root / "opis.txt").write_text("Wklejony opis z Practiscore\nMatch starts: November 21, 2026\n", encoding="utf-8")
    return {
        "folder_wejsciowy": source, "folder_wyjsciowy": root / "output", "plik_z_wynikami": root / "results.txt",
        "plik_z_torami": root / "tracks.txt", "plik_opisu_zawodow": root / "opis.txt",
        "folder_muzyki": root, "plik_z_tekstami": root / "texts.txt",
        "tryb_wynikow": "trening", "dodaj_napisy": "true",
    }


class MatchFieldsTests(unittest.TestCase):
    def test_form_fields_are_prepended_and_rest_is_kept(self):
        text = "Nazwa zawodów: Stara\nWklejony opis\nMatch starts: November 21, 2026\n#ipsc\n"
        result = apply_match_fields(text, {"name": "Nowa", "match_date": date(2026, 12, 1), "location": "Kraków"})
        self.assertTrue(result.startswith("Nazwa zawodów: Nowa\nData zawodów: 2026-12-01\nMiejsce: Kraków\n\n"))
        self.assertIn("Wklejony opis", result)
        self.assertIn("#ipsc", result)
        self.assertNotIn("Stara", result)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opis.txt"
            path.write_text(result, encoding="utf-8")
            data = read_match_data(path)
        self.assertEqual((data.name, data.match_date, data.location), ("Nowa", date(2026, 12, 1), "Kraków"))

    def test_result_plate_shows_only_available_fields(self):
        from results_parser import format_result_plate

        empty = {"miejsce": "", "procent": "", "punkty": "", "hf": ""}
        self.assertEqual(format_result_plate(3, {**empty, "czas": 12.45}), "STAGE 3 | Czas: 12.45s")
        self.assertEqual(format_result_plate(3, {**empty, "punkty": "76", "hf": "6.1", "czas": 12.45}),
                         "STAGE 3\nCzas: 12.45s | HF: 6.1 | Pkt: 76")
        full = {"miejsce": "5", "procent": "87.21%", "punkty": "76", "hf": "6.1", "czas": 12.45}
        self.assertEqual(format_result_plate(3, full),
                         "STAGE 3 | Miejsce: 5 (87.21%)\nCzas: 12.45s | HF: 6.1 | Pkt: 76")

    def test_results_mode_detection(self):
        self.assertEqual(detect_results_mode("1;9,00\n2;11\n")[0], "trening")
        mode, results = detect_results_mode(PRACTISCORE_PASTE, "trening")
        self.assertEqual(mode, "practiscore")
        self.assertEqual(results["3"]["czas"], 12.45)


class PlanTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _table(self):
        table = PlanTable(lambda name, role: icon(name, "#000000"))
        rows = [
            PlanRow("b.mp4", "1", "", 10.0, TIMER_NOT_CHECKED, "render", "Tor 1.mp4"),
            PlanRow("a.mp4", "2", "H", None, TIMER_NOT_FOUND, "skip_no_result", "Tor 2.mp4"),
        ]
        table.set_rows(rows, "V")
        return table

    def test_rows_are_ordered_by_track_and_mapping_by_file_name(self):
        table = self._table()
        self.assertEqual([row.file_name for row in table.rows()], ["b.mp4", "a.mp4"])
        self.assertEqual(table.mapping(), [("2", "H"), ("1", "")])
        self.assertIn("Do montażu: 1 z 2", table.summary.text())

    def test_move_swaps_tracks_and_emits_mapping(self):
        table = self._table()
        emitted = []
        table.mapping_changed.connect(emitted.append)
        table.table.selectRow(1)  # a.mp4, tor 2
        table._move_selected(-1)
        self.assertEqual(emitted[-1], [("1", "H"), ("2", "")])
        self.assertEqual(table.rows()[0].file_name, "a.mp4")

    def test_invalid_track_is_rejected(self):
        table = self._table()
        emitted = []
        table.mapping_changed.connect(emitted.append)
        table.table.item(0, 1).setText("abc")
        self.assertEqual(emitted, [])
        self.assertEqual(table.table.item(0, 1).text(), "1")
        table.table.item(0, 1).setText("7")
        self.assertEqual(emitted[-1], [("2", "H"), ("7", "")])

    def test_order_field_shows_order_by_file_name(self):
        table = self._table()
        self.assertEqual(table.order_edit.text(), "2,1")

    def test_order_field_sets_all_tracks_and_keeps_orientation(self):
        table = self._table()
        emitted = []
        table.mapping_changed.connect(emitted.append)
        table.order_edit.setText("5 6")
        table.apply_order()
        self.assertEqual(emitted[-1], [("5", "H"), ("6", "")])
        self.assertEqual(table.order_edit.text(), "5,6")
        self.assertTrue(table.order_error.isHidden())

    def test_order_field_rejects_wrong_count_and_duplicates(self):
        table = self._table()
        emitted = []
        table.mapping_changed.connect(emitted.append)
        table.order_edit.setText("3,3")
        table.apply_order()
        self.assertEqual(emitted, [])
        self.assertIn("powtarzają: 3", table.order_error.text())
        self.assertEqual(table.mapping(), [("2", "H"), ("1", "")])

    def test_parse_track_order(self):
        self.assertEqual(parse_track_order("5,6,7,8,1,2,3,4", 8), (["5", "6", "7", "8", "1", "2", "3", "4"], ""))
        self.assertEqual(parse_track_order(" 05; 2 ", 2), (["5", "2"], ""))
        self.assertIn("nagrań jest 3", parse_track_order("1,2", 3)[1])
        self.assertIn("x", parse_track_order("1,x", 2)[1])
        self.assertIn("0", parse_track_order("1,0", 2)[1])


class StepWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_steps_plan_and_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {key: str(value) for key, value in _project(root).items()}
            window = _window(values)
            for key in window.EDITORS:
                window._load_file(key[0], False)
            self.assertEqual([window.tabs.widget(i) for i in range(4)],
                             [window.tab_competition, window.tab_results, window.tab_main, window.tab_publish])

            # Wyniki: podgląd i status kroku
            self.assertEqual(window.results_preview.table.rowCount(), 2)
            self.assertEqual(window.tabs.status(desktop_app.STEP_RESULTS), STATUS_OK)

            # Plan: c.mp4 (tor 3) nie ma wyniku
            window._refresh_plan()
            actions = {row.file_name: row.action for row in window.plan_table.rows()}
            self.assertEqual(actions, {"a.mp4": "render", "b.mp4": "render", "c.mp4": "skip_no_result"})
            self.assertTrue(window.start_button.text().endswith("(2)"))
            self.assertEqual(window.tabs.status(desktop_app.STEP_ASSEMBLY), STATUS_OK)

            # Zmiana toru w tabeli zapisuje mapowanie_torow.txt
            window._on_mapping_changed([("3", ""), ("2", "H"), ("1", "")])
            self.assertEqual((root / "tracks.txt").read_text(encoding="utf-8"), "3\n2;H\n1\n")
            rows = {row.file_name: row for row in window.plan_table.rows()}
            self.assertEqual(rows["a.mp4"].action, "skip_no_result")
            self.assertEqual(rows["b.mp4"].orientation, "H")
            window.close()

    def test_competition_form_writes_description_and_keeps_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {key: str(value) for key, value in _project(root).items()}
            window = _window(values)
            window._load_file("plik_opisu_zawodow", False)
            self.assertEqual(window.competition_form.data()["match_date"], date(2026, 11, 21))
            self.assertEqual(window.tabs.status(desktop_app.STEP_COMPETITION), STATUS_OK)
            window._on_competition_form_changed({"name": "Liga ZSD", "match_date": date(2026, 11, 22),
                                                  "location": "", "match_type": "", "level": ""})
            text = (root / "opis.txt").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("Nazwa zawodów: Liga ZSD\nData zawodów: 2026-11-22\n"))
            self.assertIn("Wklejony opis z Practiscore", text)
            self.assertIn("2026-11-22 - Liga ZSD - Tor 1", window.competition_form.title_preview.text())
            window.close()

    def test_results_format_is_detected_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {key: str(value) for key, value in _project(root).items()}
            window = _window(values)
            window.editors["plik_z_wynikami"].setPlainText(PRACTISCORE_PASTE)
            window._update_results_preview()
            self.assertEqual(window._selected_results_mode(), "practiscore")
            self.assertIn("rozpoznany automatycznie", window.results_preview.summary.text())
            window.close()

    def test_missing_source_folder_marks_step_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {key: str(value) for key, value in _project(root).items()}
            values["folder_wejsciowy"] = str(root / "missing")
            window = _window(values)
            window._refresh_plan()
            self.assertIn("Wskaż folder", window.plan_table.summary.text())
            self.assertEqual(window.tabs.status(desktop_app.STEP_COMPETITION), STATUS_WARNING)
            window.close()


if __name__ == "__main__":
    unittest.main()
