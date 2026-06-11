# ============================================================
# preprocessing.py — Modul Praproses Teks
# Mengimplementasikan FR-PP-01 s/d FR-PP-08
# ============================================================
import re
import unicodedata


def remove_urls(text: str) -> str:
    """
    FR-PP-01: Hapus semua URL dari teks.
    Menghapus http://, https://, www., dan URL tanpa prefix.
    """
    # Hapus URL dengan protokol http/https
    text = re.sub(r"https?://\S+", "", text)
    # Hapus URL dengan www.
    text = re.sub(r"www\.\S+", "", text)
    return text


def remove_mentions(text: str) -> str:
    """
    FR-PP-02: Hapus mention pengguna (@username).
    """
    text = re.sub(r"@\w+", "", text)
    return text


def remove_hashtag_symbol(text: str) -> str:
    """
    FR-PP-02: Hapus simbol # namun pertahankan kata di belakangnya.
    Contoh: #BanggaIndonesia → BanggaIndonesia
    """
    text = re.sub(r"#(\w+)", r"\1", text)
    return text


def remove_special_characters(text: str) -> str:
    """
    FR-PP-03: Hapus karakter non-alfanumerik kecuali spasi.
    Mempertahankan huruf, angka, dan spasi.
    """
    # Normalisasi karakter unicode (tangani emoji, karakter khusus)
    text = unicodedata.normalize("NFKD", text)
    # Hapus semua karakter selain huruf, angka, dan spasi
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return text


def to_lowercase(text: str) -> str:
    """
    FR-PP-04: Case folding — ubah seluruh teks ke huruf kecil.
    """
    return text.lower()


def normalize_whitespace(text: str) -> str:
    """
    FR-PP-05: Normalisasi spasi berlebih dan leading/trailing whitespace.
    """
    # Ganti multiple spasi dengan satu spasi
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def preprocess_text(raw_text: str) -> str:
    """
    Pipeline praproses teks utama (FR-PP-01 s/d FR-PP-06).
    
    Urutan operasi dijaga ketat sesuai PRD section 6.2:
    1. Hapus URL
    2. Hapus @mention
    3. Hapus simbol #
    4. Hapus karakter khusus
    5. Case folding
    6. Normalisasi spasi
    
    CATATAN: Stopword removal TIDAK dilakukan (FR-PP-06).
    Model BERT memanfaatkan konteks penuh kalimat.
    
    Returns:
        str: Teks bersih yang siap ditokenisasi
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    
    text = raw_text
    text = remove_urls(text)           # Step 1: Hapus URL
    text = remove_mentions(text)       # Step 2: Hapus @mention
    text = remove_hashtag_symbol(text) # Step 3: Hapus simbol #
    text = remove_special_characters(text)  # Step 4: Hapus karakter khusus
    text = to_lowercase(text)          # Step 5: Case folding
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
