import io
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

# --- Stub `inference` BEFORE importing app.py ---
# app.py calls load_model() (real IndoBERT, ~475MB) at module import time. Registering a
# fake module in sys.modules first means `from inference import load_model, ...` in app.py
# resolves to this stub instead, so importing app here never touches the real model.
_fake_inference = MagicMock()
_fake_inference.load_model.return_value = (MagicMock(), MagicMock())
sys.modules["inference"] = _fake_inference

import app  # noqa: E402  (must come after the sys.modules stub above)


def _no_leftover_markers(text: str) -> bool:
    return "http" not in text and "www" not in text and "#" not in text and not re.search(r"[^\x00-\x7f]", text)


class TestApiEvaluatePreprocesses(unittest.TestCase):
    """Regression test for the bypass found during the preprocessing audit:
    /api/evaluate used to feed df['teks_asli'] straight into predict_batch()."""

    def setUp(self):
        self.client = app.app.test_client()

    # api_evaluate() does a local `from inference import predict_batch` inside the route
    # function itself (shadowing the module-level app.predict_batch), so the mock must be
    # applied to the stubbed `inference` module's attribute, not `app.predict_batch`.
    @patch.object(_fake_inference, "predict_batch")
    def test_texts_reaching_model_are_already_clean(self, mock_predict_batch):
        mock_predict_batch.return_value = [
            {"predicted_label": "Positif"},
            {"predicted_label": "Netral"},
        ]
        csv_content = (
            "teks_asli,label_asli\n"
            '"Barang mantap banget!! https://toko.co #puas @seller",Positif\n'
            '"Biasa aja lah... 😐😐",Netral\n'
        )
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "eval.csv"),
        }
        resp = self.client.post("/api/evaluate", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)

        mock_predict_batch.assert_called_once()
        received_texts = mock_predict_batch.call_args.args[0]
        self.assertEqual(len(received_texts), 2)
        for t in received_texts:
            self.assertTrue(_no_leftover_markers(t), t)
            self.assertEqual(t, t.lower())


class TestApiAnalyzeExposesRawAndClean(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app.MODEL_LOADED = True

    @patch("app.predict_sentiment")
    def test_response_has_raw_and_clean_text(self, mock_predict_sentiment):
        mock_predict_sentiment.return_value = {
            "predicted_label": "Positif",
            "confidence_positive": 0.9,
            "confidence_negative": 0.05,
            "confidence_neutral": 0.05,
            "inference_time_ms": 1.0,
        }
        resp = self.client.post("/api/analyze", json={"text": "Produk bagus banget!! https://toko.co #puas"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()

        self.assertIn("raw_text", payload)
        self.assertIn("clean_text", payload)
        self.assertIn("https://toko.co", payload["raw_text"])
        self.assertTrue(_no_leftover_markers(payload["clean_text"]), payload["clean_text"])

        # predict_sentiment must have been called with the cleaned text, not the raw one.
        called_text = mock_predict_sentiment.call_args.args[0]
        self.assertTrue(_no_leftover_markers(called_text))


class TestBuildResultsPayloadExposesSkipFields(unittest.TestCase):
    def test_top_items_include_clean_text_and_skip_reason(self):
        import os
        from utils import generate_csv_output

        os.makedirs("data", exist_ok=True)
        req_id = "__test_build_payload__"
        path = f"data/{req_id}.csv"
        try:
            csv_str = generate_csv_output([
                {
                    "raw_text": "Produk oke http://x.co", "clean_text": "produk oke", "predicted_label": "Positif",
                    "confidence_positive": 0.9, "confidence_negative": 0.05, "confidence_neutral": 0.05,
                    "source": "twitter", "date": "2026-01-01", "skipped": False, "skip_reason": "",
                },
                {
                    "raw_text": "😊😊", "clean_text": "", "predicted_label": "Netral",
                    "confidence_positive": 0.0, "confidence_negative": 0.0, "confidence_neutral": 0.0,
                    "source": "twitter", "date": "2026-01-01",
                    "skipped": True, "skip_reason": "Dilewati: konten tidak cukup setelah pembersihan",
                },
            ])
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_str)

            payload = app._build_results_payload(req_id)
            top_items = payload["top_items"]
            self.assertEqual(len(top_items), 2)

            skipped_item = next(i for i in top_items if i["skipped"])
            self.assertEqual(skipped_item["clean_text"], "")
            self.assertIn("Dilewati", skipped_item["skip_reason"])

            normal_item = next(i for i in top_items if not i["skipped"])
            self.assertEqual(normal_item["clean_text"], "produk oke")
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestApiScrapeEchoesKeyword(unittest.TestCase):
    """Regression test for the keyword-integrity guard: the frontend compares
    the keyword it sent against this echoed value before starting to poll, so
    the response must always reflect exactly what will be used for scraping."""

    def setUp(self):
        self.client = app.app.test_client()
        app.MODEL_LOADED = True

    @patch("app.threading.Thread")
    def test_response_echoes_stripped_keyword(self, mock_thread):
        resp = self.client.post("/api/scrape", json={"keyword": "  koperasi desa merah putih  "})
        self.assertEqual(resp.status_code, 202)
        payload = resp.get_json()
        self.assertEqual(payload["keyword"], "koperasi desa merah putih")
        mock_thread.assert_called_once()

    @patch("app.threading.Thread")
    def test_keyword_is_html_escaped_in_response(self, mock_thread):
        resp = self.client.post("/api/scrape", json={"keyword": "<script>alert(1)</script>"})
        self.assertEqual(resp.status_code, 202)
        payload = resp.get_json()
        self.assertNotIn("<script>", payload["keyword"])


if __name__ == "__main__":
    unittest.main()
