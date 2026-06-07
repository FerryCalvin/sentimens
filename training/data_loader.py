# ============================================================
# training/data_loader.py — Loader untuk Dataset Multi-Domain
# Mengimplementasikan strategi Section 6.3 PRD
# ============================================================
"""
Dataset yang digunakan (Tabel 6.3):
1. IndoNLU SmSA  — Ulasan Produk & Berita (~33%)
2. NusaX-Senti   — Lintas domain, lintas bahasa (~33%)
3. Kaggle Reviews — Ulasan & Media Sosial, slang/code-mixing (~33%)
"""
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from datasets import load_dataset, concatenate_datasets, Dataset, DatasetDict
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

# ---- Label Mapping ----
# Standarisasi label ke 3 kelas: 0=Negatif, 1=Netral, 2=Positif
LABEL2ID = {"negatif": 0, "netral": 1, "positif": 2}
ID2LABEL = {0: "Negatif", 1: "Netral", 2: "Positif"}

# Mapping untuk setiap dataset sumber
INDONLU_LABEL_MAP = {
    "negative": 0,
    "neutral": 1,
    "positive": 2,
    0: 0,  # negative
    1: 1,  # neutral
    2: 2,  # positive
}

NUSAX_LABEL_MAP = {
    "negative": 0,
    "neutral": 1,
    "positive": 2,
}


def load_indonlu_smsa(split: str = "all") -> pd.DataFrame:
    """
    Load dataset IndoNLU SmSA (Sentiment Analysis dari indobenchmark).
    Domain: Ulasan produk & berita, bahasa formal-terstruktur.
    
    Returns:
        DataFrame dengan kolom ['text', 'label']
    """
    logger.info("Loading IndoNLU SmSA dataset...")
    
    try:
        dataset = load_dataset("indonlp/indonlu", "smsa")
        
        dfs = []
        for split_name in ["train", "validation", "test"]:
            if split_name in dataset:
                df = dataset[split_name].to_pandas()
                df = df[["text", "label"]].copy()
                df["label"] = df["label"].map(INDONLU_LABEL_MAP)
                df["source"] = "indonlu_smsa"
                dfs.append(df)
        
        result = pd.concat(dfs, ignore_index=True)
        logger.info(f"IndoNLU SmSA: {len(result)} sampel dimuat")
        return result
        
    except Exception as e:
        logger.warning(f"Gagal load IndoNLU SmSA dari HuggingFace: {e}")
        logger.info("Mencoba load dari file lokal...")
        return _load_local_dataset("data/indonlu_smsa.csv")


def load_nusax_senti(split: str = "all", language: str = "ind") -> pd.DataFrame:
    """
    Load dataset NusaX-Senti.
    Domain: Lintas domain, bahasa Indonesia dan dialek.
    
    Args:
        language: Bahasa yang dipilih (default: 'ind' = Indonesia)
    
    Returns:
        DataFrame dengan kolom ['text', 'label']
    """
    logger.info("Loading NusaX-Senti dataset...")
    
    try:
        dataset = load_dataset("indonlp/NusaX-senti", language)
        
        dfs = []
        for split_name in ["train", "validation", "test"]:
            if split_name in dataset:
                df = dataset[split_name].to_pandas()
                df = df.rename(columns={"text": "text"})
                df["label"] = df["label"].map(NUSAX_LABEL_MAP)
                df["source"] = "nusax_senti"
                dfs.append(df)
        
        result = pd.concat(dfs, ignore_index=True)
        logger.info(f"NusaX-Senti ({language}): {len(result)} sampel dimuat")
        return result
        
    except Exception as e:
        logger.warning(f"Gagal load NusaX-Senti dari HuggingFace: {e}")
        return _load_local_dataset("data/nusax_senti.csv")


def load_kaggle_reviews(csv_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load dataset Kaggle Indonesian Sentiment Reviews.
    Domain: Ulasan & media sosial, slang, code-mixing.
    
    Args:
        csv_path: Path ke berkas CSV Kaggle (opsional)
    
    Returns:
        DataFrame dengan kolom ['text', 'label']
    """
    logger.info("Loading Kaggle Reviews dataset...")
    
    # Cari file CSV di direktori data/
    search_paths = [
        csv_path,
        "data/kaggle_reviews.csv",
        "data/indonesian_sentiment.csv",
        "data/sentiment_data.csv",
    ]
    
    for path in search_paths:
        if path and Path(path).exists():
            try:
                df = pd.read_csv(path)
                df = _normalize_kaggle_columns(df)
                df["source"] = "kaggle_reviews"
                logger.info(f"Kaggle Reviews: {len(df)} sampel dimuat dari {path}")
                return df
            except Exception as e:
                logger.warning(f"Gagal load dari {path}: {e}")
    
    logger.warning("Dataset Kaggle tidak ditemukan. Mencoba HuggingFace...")
    
    try:
        # Beberapa dataset Kaggle tersedia di HuggingFace
        dataset = load_dataset("syahra816/sentiment-analysis-id")
        df = dataset["train"].to_pandas()
        df = _normalize_kaggle_columns(df)
        df["source"] = "kaggle_hf"
        return df
    except Exception as e:
        logger.error(f"Gagal load Kaggle dataset: {e}")
        return pd.DataFrame(columns=["text", "label", "source"])


def _normalize_kaggle_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi nama kolom dari berbagai format CSV Kaggle."""
    # Cari kolom teks
    text_cols = [c for c in df.columns if any(
        kw in c.lower() for kw in ["text", "teks", "tweet", "review", "comment", "komentar"]
    )]
    label_cols = [c for c in df.columns if any(
        kw in c.lower() for kw in ["label", "sentiment", "sentimen", "class", "kelas", "category"]
    )]
    
    if not text_cols or not label_cols:
        if len(df.columns) >= 2:
            df = df.rename(columns={df.columns[0]: "text", df.columns[1]: "label"})
        else:
            raise ValueError(f"Tidak dapat mendeteksi kolom teks/label. Kolom: {df.columns.tolist()}")
    else:
        df = df.rename(columns={text_cols[0]: "text", label_cols[0]: "label"})
    
    df = df[["text", "label"]].copy()
    
    # Normalisasi label
    label_map_common = {
        "positive": 2, "pos": 2, "positif": 2, "1": 2, 1: 2,
        "negative": 0, "neg": 0, "negatif": 0, "-1": 0, -1: 0, 0: 0,
        "neutral": 1, "netral": 1, "0": 1,
    }
    
    df["label"] = df["label"].astype(str).str.lower().map(
        lambda x: label_map_common.get(x, label_map_common.get(int(x) if x.lstrip('-').isdigit() else x, None))
    )
    
    return df


def _load_local_dataset(path: str) -> pd.DataFrame:
    """Fallback: Load dataset dari file CSV lokal."""
    if not Path(path).exists():
        logger.error(f"File tidak ditemukan: {path}")
        return pd.DataFrame(columns=["text", "label", "source"])
    
    df = pd.read_csv(path)
    if "text" not in df.columns or "label" not in df.columns:
        df = _normalize_kaggle_columns(df)
    df["source"] = path
    return df


def load_all_datasets(kaggle_csv_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load dan gabungkan semua dataset dari 3 domain (strategi multi-domain).
    
    Returns:
        DataFrame gabungan yang sudah diacak
    """
    logger.info("=" * 50)
    logger.info("LOADING MULTI-DOMAIN DATASETS")
    logger.info("=" * 50)
    
    dfs = []
    
    # 1. IndoNLU SmSA
    df1 = load_indonlu_smsa()
    if not df1.empty:
        dfs.append(df1)
    
    # 2. NusaX-Senti
    df2 = load_nusax_senti()
    if not df2.empty:
        dfs.append(df2)
    
    # 3. Kaggle Reviews
    df3 = load_kaggle_reviews(kaggle_csv_path)
    if not df3.empty:
        dfs.append(df3)
    
    if not dfs:
        raise ValueError("Tidak ada dataset yang berhasil dimuat!")
    
    # Gabungkan semua dataset
    combined = pd.concat(dfs, ignore_index=True)
    
    # Hapus baris dengan nilai null
    combined = combined.dropna(subset=["text", "label"])
    combined["label"] = combined["label"].astype(int)
    
    # Hapus duplikat berdasarkan teks
    combined = combined.drop_duplicates(subset=["text"])
    
    # Hapus teks yang terlalu pendek
    combined = combined[combined["text"].str.len() >= 5]
    
    # Acak dataset
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Statistik
    logger.info("\n=== STATISTIK DATASET GABUNGAN ===")
    logger.info(f"Total sampel: {len(combined)}")
    logger.info(f"Distribusi label:")
    for label_id, label_name in ID2LABEL.items():
        count = (combined["label"] == label_id).sum()
        pct = count / len(combined) * 100
        logger.info(f"  {label_name} ({label_id}): {count} ({pct:.1f}%)")
    
    if "source" in combined.columns:
        logger.info("\nPer sumber:")
        for source, group in combined.groupby("source"):
            logger.info(f"  {source}: {len(group)} sampel")
    
    return combined


def split_dataset(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split dataset menjadi train/validation/test.
    
    Returns:
        (train_df, val_df, test_df)
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6
    
    train_df, temp_df = train_test_split(
        df,
        test_size=(val_ratio + test_ratio),
        random_state=random_state,
        stratify=df["label"],
    )
    
    relative_test_ratio = test_ratio / (val_ratio + test_ratio)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=relative_test_ratio,
        random_state=random_state,
        stratify=temp_df["label"],
    )
    
    logger.info(f"\nSplit dataset:")
    logger.info(f"  Train: {len(train_df)} ({train_ratio*100:.0f}%)")
    logger.info(f"  Validation: {len(val_df)} ({val_ratio*100:.0f}%)")
    logger.info(f"  Test: {len(test_df)} ({test_ratio*100:.0f}%)")
    
    return train_df, val_df, test_df
