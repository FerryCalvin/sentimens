import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pipeline
from utils import load_results_from_csv


def _fake_predict_batch(texts, batch_size=32, progress_cb=None):
    """Deterministic stand-in for inference.predict_batch — never touches the real model."""
    return [
        {
            "predicted_label": "Positif",
            "confidence_positive": 0.9,
            "confidence_negative": 0.05,
            "confidence_neutral": 0.05,
            "inference_time_ms": 1.0,
        }
        for _ in texts
    ]


class TestPredictValidOnly(unittest.TestCase):
    @patch("pipeline.predict_batch", side_effect=_fake_predict_batch)
    def test_skips_short_and_empty_texts_without_calling_model(self, mock_predict):
        clean_texts = ["ini bagus sekali", "", "tag", "ok", "produk jelek sekali"]
        predictions = pipeline._predict_valid_only(clean_texts)

        # Model must only ever see the texts that pass is_valid_text (len >= 3 after cleaning).
        called_texts = [t for call in mock_predict.call_args_list for t in call.args[0]]
        self.assertEqual(called_texts, ["ini bagus sekali", "tag", "produk jelek sekali"])

        self.assertFalse(predictions[0].get("skipped", False))
        self.assertTrue(predictions[1]["skipped"])
        self.assertIn("Dilewati", predictions[1]["skip_reason"])
        self.assertFalse(predictions[2].get("skipped", False))
        self.assertTrue(predictions[3]["skipped"])
        self.assertFalse(predictions[4].get("skipped", False))

    @patch("pipeline.predict_batch", side_effect=_fake_predict_batch)
    def test_empty_input_list(self, mock_predict):
        self.assertEqual(pipeline._predict_valid_only([]), [])
        mock_predict.assert_not_called()

    @patch("pipeline.predict_batch", side_effect=_fake_predict_batch)
    def test_all_invalid_never_calls_model(self, mock_predict):
        predictions = pipeline._predict_valid_only(["", "  ", "ok", "😊"])
        self.assertTrue(all(p["skipped"] for p in predictions))
        mock_predict.assert_not_called()


def _no_leftover_markers(text: str) -> bool:
    return "http" not in text and "www" not in text and "#" not in text and not re.search(r"[^\x00-\x7f]", text)


class TestRunScrapePipeline(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir_patch = patch("pipeline.DATA_DIR", Path(self._tmpdir.name))
        self._data_dir_patch.start()

    def tearDown(self):
        self._data_dir_patch.stop()
        self._tmpdir.cleanup()

    @patch("pipeline.predict_batch", side_effect=_fake_predict_batch)
    @patch("pipeline.httpx.post")
    def test_clean_text_has_no_outliers_and_skips_all_emoji_row(self, mock_post, mock_predict):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "status": "success",
            "data": [
                {"raw_text": "Produk ini bagus banget!! https://x.co #rekomen @toko", "date": "2026-01-01", "source": "twitter"},
                {"raw_text": "😊😊😊", "date": "2026-01-01", "source": "twitter"},
                {"raw_text": "Pelayanan lambat, kecewa berat www.komplain.com", "date": "2026-01-02", "source": "web"},
            ],
            "expanded_keyword": "produk",
            "plain_keyword": "produk",
            "expansion_status": "ok",
        }
        mock_post.return_value = fake_response

        result = pipeline.run_scrape_pipeline("produk", limit=10, sources=["twitter", "web"])

        self.assertEqual(result["total_results"], 3)
        rows = load_results_from_csv(result["file_path"])
        self.assertEqual(len(rows), 3)

        for row in rows:
            self.assertTrue(_no_leftover_markers(row["clean_text"]), row["clean_text"])

        emoji_row = next(r for r in rows if r["raw_text"] == "😊😊😊")
        self.assertTrue(emoji_row["skipped"])
        self.assertEqual(emoji_row["clean_text"], "")

        normal_rows = [r for r in rows if r["raw_text"] != "😊😊😊"]
        self.assertTrue(all(not r["skipped"] for r in normal_rows))


class TestRunBatchPipeline(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir_patch = patch("pipeline.DATA_DIR", Path(self._tmpdir.name))
        self._data_dir_patch.start()

    def tearDown(self):
        self._data_dir_patch.stop()
        self._tmpdir.cleanup()

    @patch("pipeline.predict_batch", side_effect=_fake_predict_batch)
    def test_batch_clean_text_and_skip_marking(self, mock_predict):
        raw_texts = [
            "Barang sesuai deskripsi, mantap!! https://toko.co #puas",
            "😊",
            "ok",
            "",
            "Kualitas buruk sekali, kecewa @seller",
        ]
        result = pipeline.run_batch_pipeline(raw_texts)
        rows = load_results_from_csv(result["file_path"])
        self.assertEqual(len(rows), 5)

        for row in rows:
            self.assertTrue(_no_leftover_markers(row["clean_text"]), row["clean_text"])

        skipped_flags = [r["skipped"] for r in rows]
        self.assertEqual(skipped_flags, [False, True, True, True, False])


if __name__ == "__main__":
    unittest.main()
