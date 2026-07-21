import re
import unittest

from preprocessing import (
    preprocess_text,
    is_valid_text,
    remove_urls,
    remove_mentions,
    remove_hashtag_symbol,
    remove_special_characters,
    to_lowercase,
    normalize_whitespace,
)


class TestIndividualSteps(unittest.TestCase):
    def test_remove_urls_strips_http_and_www(self):
        self.assertEqual(remove_urls("cek https://x.co/path ya"), "cek  ya")
        self.assertEqual(remove_urls("lihat www.berita.com sekarang"), "lihat  sekarang")

    def test_remove_mentions(self):
        self.assertEqual(remove_mentions("halo @budi apa kabar"), "halo  apa kabar")

    def test_remove_hashtag_symbol_keeps_word(self):
        self.assertEqual(remove_hashtag_symbol("#BanggaIndonesia keren"), "BanggaIndonesia keren")

    def test_remove_special_characters_strips_emoji_and_punctuation(self):
        cleaned = remove_special_characters("keren banget!! 😍😍")
        self.assertNotIn("!", cleaned)
        self.assertFalse(re.search(r"[^\x00-\x7f]", cleaned))

    def test_to_lowercase(self):
        self.assertEqual(to_lowercase("HeBoH Banget"), "heboh banget")

    def test_normalize_whitespace_collapses_and_strips(self):
        self.assertEqual(normalize_whitespace("  a    b  "), "a b")


class TestPreprocessText(unittest.TestCase):
    def test_full_pipeline_removes_all_outliers(self):
        raw = "Cek ini https://example.com/path?q=1 keren banget!! 😍😍 #trending @someone"
        cleaned = preprocess_text(raw)
        self.assertNotIn("http", cleaned)
        self.assertNotIn("www", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("@", cleaned)
        self.assertFalse(re.search(r"[^\x00-\x7f]", cleaned), "emoji/non-ascii should be stripped")
        self.assertEqual(cleaned, cleaned.lower())

    def test_www_and_multiple_emoji(self):
        cleaned = preprocess_text("www.berita.com sudah baca? #viral 🔥🔥")
        self.assertNotIn("www", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertFalse(re.search(r"[^\x00-\x7f]", cleaned))

    def test_none_and_non_str_input_returns_empty(self):
        self.assertEqual(preprocess_text(None), "")
        self.assertEqual(preprocess_text(""), "")
        self.assertEqual(preprocess_text(123), "")

    def test_emoji_only_text_becomes_empty(self):
        self.assertEqual(preprocess_text("😊😊😊"), "")

    def test_idempotent(self):
        raw = "Halo Dunia!! https://x.co #tag @user 😊"
        once = preprocess_text(raw)
        twice = preprocess_text(once)
        self.assertEqual(once, twice)


class TestIsValidText(unittest.TestCase):
    def test_empty_and_emoji_only_invalid(self):
        self.assertFalse(is_valid_text(""))
        self.assertFalse(is_valid_text(None))
        self.assertFalse(is_valid_text("😊😊😊"))

    def test_below_min_chars_after_cleaning_invalid(self):
        # "@user #tag" -> preprocess_text -> "tag" per current hashtag rule; use shorter case
        self.assertFalse(is_valid_text("ok"))  # 2 chars < default min_chars=3
        self.assertFalse(is_valid_text("@user"))  # cleans to "" (mention stripped)

    def test_at_or_above_min_chars_valid(self):
        self.assertTrue(is_valid_text("tag"))  # exactly 3 chars
        self.assertTrue(is_valid_text("Ini bagus sekali!! https://x.co"))

    def test_custom_min_chars(self):
        self.assertTrue(is_valid_text("ok", min_chars=2))
        self.assertFalse(is_valid_text("ok", min_chars=5))

    def test_idempotent_on_already_clean_text(self):
        raw = "Ini bagus sekali https://x.co"
        clean = preprocess_text(raw)
        # is_valid_text re-runs preprocess_text internally; must agree on already-clean input
        self.assertEqual(is_valid_text(raw), is_valid_text(clean))


if __name__ == "__main__":
    unittest.main()
