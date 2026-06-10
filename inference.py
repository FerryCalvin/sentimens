# ============================================================
# inference.py — Modul Inferensi IndoBERT
# Mengimplementasikan FR-AI-01 s/d FR-AI-05
# ============================================================
import time
import logging
from pathlib import Path

import torch
from transformers import BertForSequenceClassification, AutoTokenizer

from config import (
    MODEL_PATH,
    TOKENIZER_PATH,
    MAX_TOKEN_LENGTH,
    LABEL_MAP,
)

logger = logging.getLogger(__name__)

# ---- Global model instance (dimuat sekali saat startup) ----
_model: BertForSequenceClassification | None = None
_tokenizer = None
_device: torch.device = torch.device("cpu")


def load_model():
    """
    FR-AI-01: Muat model dan tokenizer ke RAM pada saat startup.
    Model dimuat SEKALI dan disimpan sebagai global variable.
    
    Returns:
        Tuple (model, tokenizer)
        
    Raises:
        FileNotFoundError: Jika file model tidak ditemukan
        RuntimeError: Jika terjadi error saat memuat model
    """
    global _model, _tokenizer, _device
    
    if _model is not None and _tokenizer is not None:
        logger.info("Model sudah dimuat sebelumnya, menggunakan instance yang ada.")
        return _model, _tokenizer
    
    model_path = Path(MODEL_PATH)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Direktori model tidak ditemukan: {MODEL_PATH}\n"
            "Pastikan folder 'models/' berisi file model yang valid."
        )
    
    logger.info(f"Memuat tokenizer dari: {TOKENIZER_PATH}")
    _tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
    
    logger.info(f"Memuat model dari: {MODEL_PATH}")
    _model = BertForSequenceClassification.from_pretrained(MODEL_PATH)
    
    # Gunakan GPU jika tersedia, fallback ke CPU
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model = _model.to(_device)
    
    # FR-AI-02: Set ke mode evaluasi (nonaktifkan dropout)
    _model.eval()
    
    logger.info(f"Model berhasil dimuat. Device: {_device}")
    logger.info(f"Jumlah label: {_model.config.num_labels}")
    
    return _model, _tokenizer


def get_model():
    """
    Dapatkan instance model yang sudah dimuat.
    Memanggil load_model() jika belum dimuat.
    """
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        return load_model()
    return _model, _tokenizer


def predict_sentiment(clean_text: str) -> dict:
    """
    FR-AI-02 s/d FR-AI-05: Jalankan inferensi pada teks yang sudah dipreprocess.
    
    Args:
        clean_text: Teks yang sudah melalui praproses
        
    Returns:
        dict dengan format sesuai FR-AI-05:
        {
            "predicted_label": str,         # "Positif" | "Negatif" | "Netral"
            "confidence_positive": float,   # 0.0 - 1.0
            "confidence_negative": float,   # 0.0 - 1.0
            "confidence_neutral": float,    # 0.0 - 1.0
            "inference_time_ms": float,     # waktu inferensi dalam ms
            "label_index": int              # index label (0, 1, 2)
        }
    """
    model, tokenizer = get_model()
    
    # Handle teks kosong
    if not clean_text or not clean_text.strip():
        return {
            "predicted_label": "Netral",
            "confidence_positive": 0.333,
            "confidence_negative": 0.333,
            "confidence_neutral": 0.334,
            "inference_time_ms": 0.0,
            "label_index": 1,
        }
    
    start_time = time.perf_counter()
    
    # FR-PP-07 & FR-PP-08: Tokenisasi dengan truncation dan padding
    encoding = tokenizer(
        clean_text,
        max_length=MAX_TOKEN_LENGTH,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    
    # Pindahkan tensor ke device yang sesuai
    input_ids = encoding["input_ids"].to(_device)
    attention_mask = encoding["attention_mask"].to(_device)
    
    # FR-AI-02: Jalankan inferensi dalam mode no_grad
    with torch.no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    
    # FR-AI-03: Normalisasi probabilitas dengan softmax
    logits = outputs.logits
    probs = torch.softmax(logits, dim=-1).squeeze()
    
    # FR-AI-04: Ambil label dengan probabilitas tertinggi
    label_idx = torch.argmax(probs).item()
    
    end_time = time.perf_counter()
    inference_time_ms = (end_time - start_time) * 1000
    
    # Konversi tensor ke Python float
    probs_list = probs.cpu().tolist()
    
    # Mapping index ke nilai confidence per kelas
    # LABEL_0 → Negatif (index 0)
    # LABEL_1 → Netral  (index 1)
    # LABEL_2 → Positif (index 2)
    confidence_negative = round(float(probs_list[0]), 4)
    confidence_neutral = round(float(probs_list[1]), 4)
    confidence_positive = round(float(probs_list[2]), 4)
    
    predicted_label = LABEL_MAP.get(label_idx, "Netral")
    
    return {
        "predicted_label": predicted_label,
        "confidence_positive": confidence_positive,
        "confidence_negative": confidence_negative,
        "confidence_neutral": confidence_neutral,
        "inference_time_ms": round(inference_time_ms, 2),
        "label_index": label_idx,
    }


def predict_batch(clean_texts: list[str], batch_size: int = 32) -> list[dict]:
    """
    Inferensi batch untuk efisiensi pemrosesan banyak teks.
    
    Args:
        clean_texts: List teks yang sudah dipreprocess
        batch_size: Ukuran batch untuk inferensi
        
    Returns:
        List hasil inferensi per teks
    """
    model, tokenizer = get_model()
    results = []
    
    for i in range(0, len(clean_texts), batch_size):
        batch = clean_texts[i : i + batch_size]
        
        # Handle teks kosong dalam batch
        valid_batch = [text if text and text.strip() else "[PAD]" for text in batch]
        
        # Tokenisasi batch sekaligus
        encodings = tokenizer(
            valid_batch,
            max_length=MAX_TOKEN_LENGTH,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        
        input_ids = encodings["input_ids"].to(_device)
        attention_mask = encodings["attention_mask"].to(_device)

        logger.debug(f"[predict_batch] batch {i//batch_size + 1}: {len(batch)} items — running model...")
        start_time = time.perf_counter()

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        end_time = time.perf_counter()
        batch_time_ms = (end_time - start_time) * 1000
        per_item_time = batch_time_ms / len(batch)
        logger.debug(f"[predict_batch] batch done: {batch_time_ms:.0f}ms ({per_item_time:.0f}ms/item)")
        
        probs_batch = torch.softmax(outputs.logits, dim=-1).cpu()
        
        for j, probs in enumerate(probs_batch):
            probs_list = probs.tolist()
            label_idx = int(torch.argmax(probs).item())
            
            # Tandai teks asli yang kosong
            original_was_empty = not clean_texts[i + j] or not clean_texts[i + j].strip()
            
            results.append({
                "predicted_label": LABEL_MAP.get(label_idx, "Netral"),
                "confidence_positive": round(float(probs_list[2]), 4),
                "confidence_negative": round(float(probs_list[0]), 4),
                "confidence_neutral": round(float(probs_list[1]), 4),
                "inference_time_ms": round(per_item_time, 2),
                "label_index": label_idx,
                "skipped": original_was_empty,
            })
    
    return results
