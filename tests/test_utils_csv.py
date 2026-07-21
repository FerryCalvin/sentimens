import os
import tempfile
import unittest

from config import CSV_OUTPUT_COLUMNS
from utils import (
    generate_csv_output,
    load_results_from_csv,
    load_dataframe,
    get_top_items,
    _available_output_columns,
)

OLD_FORMAT_HEADER = "teks_asli,teks_bersih,sentimen,confidence_positif,confidence_negatif,confidence_netral,source,date"
OLD_FORMAT_ROW = 'produk bagus,produk bagus,Positif,0.9,0.05,0.05,twitter,2026-01-01'


class TempCsvMixin:
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name: str, content: str) -> str:
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(content)
        return path


class TestGenerateCsvOutput(unittest.TestCase):
    def test_writes_skip_columns(self):
        csv_str = generate_csv_output([
            {
                "raw_text": "bagus banget", "clean_text": "bagus banget", "predicted_label": "Positif",
                "confidence_positive": 0.9, "confidence_negative": 0.05, "confidence_neutral": 0.05,
                "source": "twitter", "date": "2026-01-01", "skipped": False, "skip_reason": "",
            },
            {
                "raw_text": "😊", "clean_text": "", "predicted_label": "Netral",
                "confidence_positive": 0.0, "confidence_negative": 0.0, "confidence_neutral": 0.0,
                "source": "twitter", "date": "2026-01-01",
                "skipped": True, "skip_reason": "Dilewati: konten tidak cukup setelah pembersihan",
            },
        ])
        lines = csv_str.strip().splitlines()
        self.assertEqual(lines[0], ",".join(CSV_OUTPUT_COLUMNS))
        self.assertIn("False", lines[1])
        self.assertIn("True", lines[2])
        self.assertIn("Dilewati", lines[2])


class TestAvailableOutputColumns(TempCsvMixin, unittest.TestCase):
    def test_old_format_intersection(self):
        path = self._write("old.csv", OLD_FORMAT_HEADER + "\n" + OLD_FORMAT_ROW + "\n")
        cols = _available_output_columns(path)
        self.assertEqual(cols, [
            "teks_asli", "teks_bersih", "sentimen",
            "confidence_positif", "confidence_negatif", "confidence_netral",
            "source", "date",
        ])
        self.assertNotIn("dilewati", cols)

    def test_new_format_intersection(self):
        csv_str = generate_csv_output([{
            "raw_text": "a", "clean_text": "a", "predicted_label": "Netral",
            "confidence_positive": 0.0, "confidence_negative": 0.0, "confidence_neutral": 0.0,
            "source": "twitter", "date": "2026-01-01", "skipped": False, "skip_reason": "",
        }])
        path = self._write("new.csv", csv_str)
        cols = _available_output_columns(path)
        self.assertEqual(cols, CSV_OUTPUT_COLUMNS)


class TestLoadResultsFromCsv(TempCsvMixin, unittest.TestCase):
    def test_backward_compat_old_format(self):
        path = self._write("old.csv", OLD_FORMAT_HEADER + "\n" + OLD_FORMAT_ROW + "\n")
        rows = load_results_from_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_text"], "produk bagus")
        self.assertFalse(rows[0]["skipped"])
        self.assertEqual(rows[0]["skip_reason"], "")

    def test_new_format_roundtrip(self):
        csv_str = generate_csv_output([{
            "raw_text": "😊😊", "clean_text": "", "predicted_label": "Netral",
            "confidence_positive": 0.0, "confidence_negative": 0.0, "confidence_neutral": 0.0,
            "source": "twitter", "date": "2026-01-01",
            "skipped": True, "skip_reason": "Dilewati: konten tidak cukup setelah pembersihan",
        }])
        path = self._write("new.csv", csv_str)
        rows = load_results_from_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["skipped"])
        self.assertEqual(rows[0]["skip_reason"], "Dilewati: konten tidak cukup setelah pembersihan")


class TestLoadDataframe(TempCsvMixin, unittest.TestCase):
    def _resolve(self, name):
        # load_dataframe resolves paths as data/<request_id>.csv; point DATA_DIR-independent
        # resolution by writing straight into the shared 'data' folder under a throwaway id,
        # then clean it up — keeps the test self-contained without patching module internals.
        return name

    def test_old_and_new_format_both_load(self):
        os.makedirs("data", exist_ok=True)
        old_id = "__test_old_fmt__"
        new_id = "__test_new_fmt__"
        old_path = f"data/{old_id}.csv"
        new_path = f"data/{new_id}.csv"
        try:
            with open(old_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(OLD_FORMAT_HEADER + "\n" + OLD_FORMAT_ROW + "\n")
            csv_str = generate_csv_output([{
                "raw_text": "mantap", "clean_text": "mantap", "predicted_label": "Positif",
                "confidence_positive": 0.9, "confidence_negative": 0.05, "confidence_neutral": 0.05,
                "source": "twitter", "date": "2026-01-01", "skipped": False, "skip_reason": "",
            }])
            with open(new_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_str)

            df_old = load_dataframe(old_id)
            df_new = load_dataframe(new_id)
            self.assertEqual(len(df_old), 1)
            self.assertEqual(len(df_new), 1)
            self.assertNotIn("dilewati", df_old.columns)
            self.assertIn("dilewati", df_new.columns)
        finally:
            for p in (old_path, new_path):
                if os.path.exists(p):
                    os.remove(p)


class TestGetTopItems(TempCsvMixin, unittest.TestCase):
    def test_includes_clean_text_and_skip_when_present(self):
        os.makedirs("data", exist_ok=True)
        req_id = "__test_top_items_new__"
        path = f"data/{req_id}.csv"
        try:
            csv_str = generate_csv_output([{
                "raw_text": "produk bagus http://x.co", "clean_text": "produk bagus", "predicted_label": "Positif",
                "confidence_positive": 0.9, "confidence_negative": 0.05, "confidence_neutral": 0.05,
                "source": "twitter", "date": "2026-01-01", "skipped": False, "skip_reason": "",
            }])
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_str)
            df = load_dataframe(req_id)
            items = get_top_items(df, n=10)
            self.assertEqual(len(items), 1)
            self.assertIn("teks_bersih", items[0])
            self.assertIn("dilewati", items[0])
            self.assertEqual(items[0]["teks_bersih"], "produk bagus")
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_old_format_does_not_error_and_omits_new_cols(self):
        os.makedirs("data", exist_ok=True)
        req_id = "__test_top_items_old__"
        path = f"data/{req_id}.csv"
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(OLD_FORMAT_HEADER + "\n" + OLD_FORMAT_ROW + "\n")
            df = load_dataframe(req_id)
            items = get_top_items(df, n=10)
            self.assertEqual(len(items), 1)
            self.assertNotIn("dilewati", items[0])
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
