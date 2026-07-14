# ============================================================
# preprocessing.py — Modul Praproses Teks
# Mengimplementasikan FR-PP-01 s/d FR-PP-08
# ============================================================
import re
import unicodedata

_RE_URL        = re.compile(r"http\S+|www\S+")
_RE_MENTION    = re.compile(r"@[a-z0-9_]+")
_RE_HASHTAG    = re.compile(r"#\w+")
_RE_NON_ALPHA  = re.compile(r"[^a-z\s]")
_RE_WHITESPACE = re.compile(r"\s+")


def to_lowercase(text: str) -> str:
    """
    FR-PP-04: Case folding — ubah seluruh teks ke huruf kecil.
    """
    return text.lower()


def remove_urls(text: str) -> str:
    """
    FR-PP-01: Hapus semua URL dari teks (http, https, www).
    """
    return _RE_URL.sub("", text)


def remove_mentions(text: str) -> str:
    """
    FR-PP-02: Hapus mention pengguna (@username).
    """
    return _RE_MENTION.sub("", text)


def remove_hashtag_symbol(text: str) -> str:
    """
    FR-PP-02: Hapus tagar beserta kata di belakangnya (simbol # dan kata dihapus total).
    Contoh: #BanggaIndonesia → (dihapus seluruhnya)
    """
    return _RE_HASHTAG.sub("", text)


def remove_special_characters(text: str) -> str:
    """
    FR-PP-03: Hapus karakter non-alfabet (termasuk angka) kecuali spasi.
    Mempertahankan huruf dan spasi saja.
    """
    # Normalisasi karakter unicode (tangani aksen/karakter khusus)
    text = unicodedata.normalize("NFKD", text)
    # Hapus semua karakter selain huruf dan spasi
    text = _RE_NON_ALPHA.sub(" ", text)
    return text


def normalize_whitespace(text: str) -> str:
    """
    FR-PP-05: Normalisasi spasi berlebih dan leading/trailing whitespace.
    """
    # Ganti multiple spasi dengan satu spasi
    text = _RE_WHITESPACE.sub(" ", text)
    return text.strip()


def preprocess_text(raw_text: str) -> str:
    """
    Pipeline praproses teks utama (FR-PP-01 s/d FR-PP-06).

    Urutan operasi dijaga ketat sesuai Tabel 4.7 skripsi:
    1. Case folding
    2. Hapus URL
    3. Hapus @mention
    4. Hapus tagar (simbol + kata)
    5. Hapus karakter non-alfabet (termasuk angka)
    6. Normalisasi spasi

    CATATAN: Stopword removal TIDAK dilakukan (FR-PP-06).
    Model BERT memanfaatkan konteks penuh kalimat.

    Returns:
        str: Teks bersih yang siap ditokenisasi
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text
    text = to_lowercase(text)          # Step 1: Case folding
    text = remove_urls(text)           # Step 2: Hapus URL
    text = remove_mentions(text)       # Step 3: Hapus @mention
    text = remove_hashtag_symbol(text) # Step 4: Hapus tagar (simbol + kata)
    text = remove_special_characters(text)  # Step 5: Hapus karakter non-alfabet
    text = normalize_whitespace(text)  # Step 6: Normalisasi spasi
    # TIDAK ada stopword removal (FR-PP-06)
    return text


def is_valid_text(text: str, min_chars: int = 3) -> bool:
    """
    Validasi apakah teks cukup valid untuk dianalisis.
    
    Args:
        text: Teks yang akan divalidasi
        min_chars: Jumlah karakter minimum setelah praproses
        
    Returns:
        bool: True jika teks valid
    """
    if not text or not isinstance(text, str):
        return False
    cleaned = preprocess_text(text)
    return len(cleaned) >= min_chars


def get_word_frequencies(texts: list[str]) -> dict[str, int]:
    """
    Hitung frekuensi kata dari list teks (untuk word cloud).
    
    Args:
        texts: List teks yang sudah dipreprocess
        
    Returns:
        dict: {kata: frekuensi}
    """
    word_freq: dict[str, int] = {}
    
    # Stopwords (untuk word cloud saja, bukan analisis)
    stopwords_wc = {
        # Indonesia
        "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan",
        "adalah", "untuk", "atau", "pada", "tidak", "juga", "dalam",
        "ada", "akan", "saya", "kami", "kita", "mereka",
        "dia", "ia", "anda", "kamu", "bisa", "sudah",
        "lebih", "sangat", "telah", "saat",
        "hanya", "jadi", "agar", "karena", "maka", "jika",
        "tapi", "namun", "bahwa", "nya", "pun", "lagi",
        "belum", "masih", "pernah", "selalu", "sering", "jarang",
        "mau", "ingin", "perlu", "harus", "boleh", "bukan",
        "sama", "seperti", "yaitu", "serta", "baik", "hal",
        # English function words
        "the", "was", "is", "are", "for", "with", "from", "has", "have", "been",
        "that", "this", "but", "not", "you", "him", "her", "its", "they", "our",
        "who", "can", "had", "what", "how", "when", "were", "will", "would", "could",
        "should", "their", "there", "them", "all", "any", "also", "just", "into",
        "then", "than", "more", "some", "such", "these", "those", "after", "before",
        "while", "about", "said", "over", "under", "each", "out", "one", "two",
    }
    
    for text in texts:
        if not text:
            continue
        words = text.split()
        for word in words:
            word = word.strip()
            # Hanya kata dengan panjang > 2 dan bukan stopword
            if len(word) > 2 and word not in stopwords_wc:
                word_freq[word] = word_freq.get(word, 0) + 1
    
    # Urutkan berdasarkan frekuensi (descending) dan ambil top 100
    sorted_freq = dict(
        sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:100]
    )
    return sorted_freq
