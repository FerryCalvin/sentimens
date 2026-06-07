# ============================================================
# training/evaluate.py — Script Evaluasi Model IndoBERT
# Mengimplementasikan SM-02: Accuracy, Precision, Recall, F1
# ============================================================
"""
Script evaluasi model fine-tuned IndoBERT.
Menghasilkan laporan lengkap: Accuracy, Precision, Recall, F1, Confusion Matrix.

Cara menjalankan:
    python evaluate.py --model_path ../models --test_csv data/test_data.csv
    
    atau gunakan dataset otomatis:
    python evaluate.py --model_path ../models --use_auto_split
"""
import argparse
import logging
import sys
from pathlib import Path

import torch
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from torch.utils.data import DataLoader
from transformers import BertForSequenceClassification, BertTokenizer

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.train import SentimentDataset
from training.data_loader import load_all_datasets, split_dataset, ID2LABEL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def evaluate_model(
    model_path: str,
    test_df: pd.DataFrame,
    batch_size: int = 32,
    max_length: int = 512,
) -> dict:
    """
    Evaluasi model pada dataset test.
    
    Args:
        model_path: Path ke direktori model
        test_df: DataFrame test dengan kolom ['text', 'label']
        batch_size: Ukuran batch untuk inferensi
        max_length: Panjang token maksimum
    
    Returns:
        dict dengan semua metrik evaluasi
    """
    # ---- Load Model & Tokenizer ----
    logger.info(f"Memuat model dari: {model_path}")
    
    tokenizer = BertTokenizer.from_pretrained(model_path)
    model = BertForSequenceClassification.from_pretrained(model_path)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()
    
    logger.info(f"Device: {device}")
    logger.info(f"Jumlah parameter: {sum(p.numel() for p in model.parameters()):,}")
    
    # ---- Buat Dataset & DataLoader ----
    test_dataset = SentimentDataset(
        test_df["text"].tolist(),
        test_df["label"].tolist(),
        tokenizer,
        max_length,
    )
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    # ---- Inferensi ----
    all_preds = []
    all_labels = []
    all_probs = []
    
    logger.info(f"Menjalankan evaluasi pada {len(test_df)} sampel...")
    
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"]
            
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()
            preds = np.argmax(probs, axis=-1)
            
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
            all_probs.extend(probs)
    
    # ---- Hitung Metrik (SM-02, Section 7.2) ----
    label_names = [ID2LABEL[i] for i in range(3)]
    
    accuracy = accuracy_score(all_labels, all_preds)
    precision_macro = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    recall_macro = recall_score(all_labels, all_preds, average="macro", zero_division=0)
    f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    
    report_dict = classification_report(
        all_labels, all_preds,
        target_names=label_names,
        output_dict=True,
        zero_division=0,
    )
    
    cm = confusion_matrix(all_labels, all_preds)
    
    # ---- Cetak Laporan ----
    logger.info("\n" + "=" * 60)
    logger.info("LAPORAN EVALUASI MODEL INDOBERT")
    logger.info("=" * 60)
    
    logger.info(f"\n📊 METRIK KESELURUHAN:")
    logger.info(f"  Accuracy:          {accuracy*100:.2f}%  {'✅' if accuracy >= 0.80 else '⚠️'} (Target: ≥ 80%)")
    logger.info(f"  Precision (Macro): {precision_macro*100:.2f}%  {'✅' if precision_macro >= 0.78 else '⚠️'} (Target: ≥ 78%)")
    logger.info(f"  Recall (Macro):    {recall_macro*100:.2f}%  {'✅' if recall_macro >= 0.78 else '⚠️'} (Target: ≥ 78%)")
    logger.info(f"  F1-Score (Macro):  {f1_macro*100:.2f}%  {'✅' if f1_macro >= 0.79 else '⚠️'} (Target: ≥ 79%)")
    
    logger.info(f"\n📋 METRIK PER KELAS:")
    logger.info(f"  {'Kelas':<10} {'Precision':>10} {'Recall':>10} {'F1-Score':>10} {'Support':>10}")
    logger.info(f"  {'-'*50}")
    
    for label in label_names:
        if label in report_dict:
            r = report_dict[label]
            logger.info(f"  {label:<10} {r['precision']*100:>9.2f}% {r['recall']*100:>9.2f}% {r['f1-score']*100:>9.2f}% {r['support']:>10.0f}")
    
    logger.info(f"\n🔢 CONFUSION MATRIX:")
    logger.info(f"  (Baris = Label Aktual, Kolom = Label Prediksi)")
    logger.info(f"  {'':>10} " + " ".join(f"{'Pred '+l:>12}" for l in label_names))
    for i, label in enumerate(label_names):
        row = " ".join(f"{cm[i,j]:>12}" for j in range(3))
        logger.info(f"  {'Aktual '+label:>10} {row}")
    
    # Verifikasi semua target terpenuhi
    all_targets_met = (
        accuracy >= 0.80 and
        precision_macro >= 0.78 and
        recall_macro >= 0.78 and
        f1_macro >= 0.79
    )
    
    if all_targets_met:
        logger.info("\n🎉 SEMUA TARGET METRIK TERPENUHI! Model siap untuk demonstrasi sidang.")
    else:
        logger.warning("\n⚠️ Beberapa target metrik belum terpenuhi. Pertimbangkan fine-tuning lebih lanjut.")
    
    return {
        "accuracy": accuracy,
        "precision_macro": precision_macro,
        "recall_macro": recall_macro,
        "f1_macro": f1_macro,
        "classification_report": report_dict,
        "confusion_matrix": cm.tolist(),
        "all_targets_met": all_targets_met,
        "predictions": all_preds,
        "true_labels": all_labels,
        "probabilities": all_probs,
    }


def plot_confusion_matrix(
    cm: list,
    label_names: list,
    output_path: str = "training/confusion_matrix.png",
) -> None:
    """Generate dan simpan visualisasi confusion matrix."""
    cm_array = np.array(cm)
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm_array,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=label_names,
        yticklabels=label_names,
        linewidths=0.5,
        linecolor="lightgray",
    )
    plt.title("Confusion Matrix — IndoBERT Sentiment Classification", fontsize=14, fontweight="bold")
    plt.ylabel("Label Aktual", fontsize=12)
    plt.xlabel("Label Prediksi", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    
    logger.info(f"✓ Confusion matrix disimpan: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluasi model IndoBERT fine-tuned")
    parser.add_argument("--model_path", type=str, default="../models",
                        help="Path ke direktori model")
    parser.add_argument("--test_csv", type=str, default=None,
                        help="Path ke berkas CSV test (opsional)")
    parser.add_argument("--use_auto_split", action="store_true",
                        help="Gunakan split otomatis dari dataset gabungan")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--output_dir", type=str, default="training",
                        help="Direktori untuk menyimpan output evaluasi")
    parser.add_argument("--kaggle_csv", type=str, default=None)
    
    args = parser.parse_args()
    
    # ---- Muat Data Test ----
    if args.test_csv and Path(args.test_csv).exists():
        logger.info(f"Memuat data test dari: {args.test_csv}")
        test_df = pd.read_csv(args.test_csv)
    elif args.use_auto_split:
        logger.info("Menggunakan auto-split dari dataset gabungan...")
        df = load_all_datasets(args.kaggle_csv)
        _, _, test_df = split_dataset(df)
    else:
        logger.error(
            "Tentukan --test_csv atau gunakan --use_auto_split.\n"
            "Contoh: python evaluate.py --model_path ../models --use_auto_split"
        )
        sys.exit(1)
    
    logger.info(f"Data test: {len(test_df)} sampel")
    
    # ---- Evaluasi ----
    results = evaluate_model(
        model_path=args.model_path,
        test_df=test_df,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    
    # ---- Simpan Confusion Matrix ----
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    label_names = [ID2LABEL[i] for i in range(3)]
    
    cm_path = f"{args.output_dir}/confusion_matrix.png"
    try:
        plot_confusion_matrix(results["confusion_matrix"], label_names, cm_path)
    except Exception as e:
        logger.warning(f"Gagal membuat confusion matrix plot: {e}")
    
    # ---- Simpan Hasil CSV ----
    results_df = pd.DataFrame({
        "true_label": results["true_labels"],
        "predicted_label": results["predictions"],
        "confidence_negatif": [p[0] for p in results["probabilities"]],
        "confidence_netral": [p[1] for p in results["probabilities"]],
        "confidence_positif": [p[2] for p in results["probabilities"]],
    })
    
    results_path = f"{args.output_dir}/evaluation_results.csv"
    results_df.to_csv(results_path, index=False)
    logger.info(f"✓ Hasil evaluasi disimpan: {results_path}")


if __name__ == "__main__":
    main()
