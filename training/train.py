# ============================================================
# training/train.py — Script Fine-Tuning IndoBERT Multi-Domain
# ============================================================
"""
Melatih ulang IndoBERT dengan strategi multi-domain:
- Base model: indobenchmark/indobert-base-p1
- Dataset: IndoNLU SmSA + NusaX-Senti + Kaggle Reviews
- Output: models/ (siap digunakan oleh Flask app)

Cara menjalankan:
    cd training
    python train.py --epochs 3 --batch_size 16 --lr 2e-5
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

import torch
import numpy as np
from torch.utils.data import Dataset as TorchDataset, DataLoader
from transformers import (
    BertForSequenceClassification,
    BertTokenizer,
    AdamW,
    get_linear_schedule_with_warmup,
)
from sklearn.metrics import accuracy_score, classification_report

# Tambahkan root project ke path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.data_loader import load_all_datasets, split_dataset, LABEL2ID, ID2LABEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("training/training_log.txt"),
    ]
)
logger = logging.getLogger(__name__)

# ---- Default Konfigurasi ----
DEFAULT_MODEL_NAME = "indobenchmark/indobert-base-p1"
DEFAULT_OUTPUT_DIR = "models"
DEFAULT_MAX_LENGTH = 512
DEFAULT_EPOCHS = 3
DEFAULT_BATCH_SIZE = 16
DEFAULT_LR = 2e-5
DEFAULT_WARMUP_RATIO = 0.1
DEFAULT_WEIGHT_DECAY = 0.01


class SentimentDataset(TorchDataset):
    """PyTorch Dataset untuk data sentimen."""
    
    def __init__(self, texts: list[str], labels: list[int], tokenizer: BertTokenizer, max_length: int):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": torch.tensor(label, dtype=torch.long),
        }


def train_epoch(
    model: BertForSequenceClassification,
    dataloader: DataLoader,
    optimizer,
    scheduler,
    device: torch.device,
) -> tuple[float, float]:
    """Satu epoch training."""
    model.train()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    
    for step, batch in enumerate(dataloader):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)
        
        optimizer.zero_grad()
        
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )
        
        loss = outputs.loss
        logits = outputs.logits
        
        loss.backward()
        
        # Gradient clipping untuk stabilitas training
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        scheduler.step()
        
        total_loss += loss.item()
        preds = torch.argmax(logits, dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())
        
        if step % 50 == 0:
            logger.info(f"  Step {step}/{len(dataloader)} | Loss: {loss.item():.4f}")
    
    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_labels, all_preds)
    
    return avg_loss, accuracy


def evaluate(
    model: BertForSequenceClassification,
    dataloader: DataLoader,
    device: torch.device,
) -> tuple[float, float, dict]:
    """Evaluasi model pada dataset validation/test."""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            
            total_loss += outputs.loss.item()
            preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())
    
    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_labels, all_preds)
    
    report = classification_report(
        all_labels,
        all_preds,
        target_names=[ID2LABEL[i] for i in range(3)],
        output_dict=True,
    )
    
    return avg_loss, accuracy, report


def train(args):
    """Fungsi training utama."""
    logger.info("=" * 60)
    logger.info("MULAI FINE-TUNING IndoBERT MULTI-DOMAIN")
    logger.info("=" * 60)
    logger.info(f"Base model: {args.model_name}")
    logger.info(f"Epochs: {args.epochs}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Learning rate: {args.lr}")
    logger.info(f"Max length: {args.max_length}")
    logger.info(f"Output dir: {args.output_dir}")
    
    # ---- Device ----
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")
    if device.type == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # ---- Load Data ----
    logger.info("\n--- Memuat Dataset Multi-Domain ---")
    df = load_all_datasets(args.kaggle_csv)
    train_df, val_df, test_df = split_dataset(df)
    
    # ---- Load Tokenizer ----
    logger.info(f"\n--- Memuat Tokenizer: {args.model_name} ---")
    tokenizer = BertTokenizer.from_pretrained(args.model_name)
    
    # ---- Buat Dataset & DataLoader ----
    train_dataset = SentimentDataset(
        train_df["text"].tolist(),
        train_df["label"].tolist(),
        tokenizer,
        args.max_length,
    )
    val_dataset = SentimentDataset(
        val_df["text"].tolist(),
        val_df["label"].tolist(),
        tokenizer,
        args.max_length,
    )
    test_dataset = SentimentDataset(
        test_df["text"].tolist(),
        test_df["label"].tolist(),
        tokenizer,
        args.max_length,
    )
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size)
    
    # ---- Load Model ----
    logger.info(f"\n--- Memuat Model: {args.model_name} ---")
    model = BertForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    model = model.to(device)
    
    # ---- Optimizer & Scheduler ----
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * DEFAULT_WARMUP_RATIO)
    
    optimizer = AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=DEFAULT_WEIGHT_DECAY,
    )
    
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    
    # ---- Training Loop ----
    best_val_accuracy = 0.0
    best_model_state = None
    
    logger.info("\n--- Mulai Training ---")
    
    for epoch in range(1, args.epochs + 1):
        logger.info(f"\n{'='*40}")
        logger.info(f"EPOCH {epoch}/{args.epochs}")
        logger.info(f"{'='*40}")
        
        start_time = time.time()
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, scheduler, device)
        
        # Validate
        val_loss, val_acc, val_report = evaluate(model, val_loader, device)
        
        epoch_time = time.time() - start_time
        
        logger.info(f"\nHasil Epoch {epoch}:")
        logger.info(f"  Train Loss: {train_loss:.4f} | Train Acc: {train_acc*100:.2f}%")
        logger.info(f"  Val Loss:   {val_loss:.4f} | Val Acc:   {val_acc*100:.2f}%")
        logger.info(f"  Waktu: {epoch_time:.1f} detik")
        
        # Simpan model terbaik
        if val_acc > best_val_accuracy:
            best_val_accuracy = val_acc
            best_model_state = model.state_dict().copy()
            logger.info(f"  ✓ Model terbaik disimpan (val_acc={val_acc*100:.2f}%)")
    
    # ---- Evaluasi Final pada Test Set ----
    logger.info("\n--- Evaluasi Final pada Test Set ---")
    
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    test_loss, test_acc, test_report = evaluate(model, test_loader, device)
    
    logger.info(f"\n=== HASIL EVALUASI TEST SET ===")
    logger.info(f"Test Accuracy: {test_acc*100:.2f}%")
    logger.info(f"Test Loss:     {test_loss:.4f}")
    logger.info(f"\nClassification Report:")
    
    for label_name in ["Negatif", "Netral", "Positif"]:
        if label_name in test_report:
            r = test_report[label_name]
            logger.info(f"  {label_name}:")
            logger.info(f"    Precision: {r['precision']*100:.2f}%")
            logger.info(f"    Recall:    {r['recall']*100:.2f}%")
            logger.info(f"    F1-Score:  {r['f1-score']*100:.2f}%")
    
    macro_avg = test_report.get("macro avg", {})
    logger.info(f"\nMacro Average:")
    logger.info(f"  Precision: {macro_avg.get('precision', 0)*100:.2f}%")
    logger.info(f"  Recall:    {macro_avg.get('recall', 0)*100:.2f}%")
    logger.info(f"  F1-Score:  {macro_avg.get('f1-score', 0)*100:.2f}%")
    
    # ---- Simpan Model ----
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"\n--- Menyimpan Model ke {output_path} ---")
    model.save_pretrained(str(output_path))
    tokenizer.save_pretrained(str(output_path))
    
    logger.info(f"✓ Model berhasil disimpan!")
    logger.info(f"  File: {list(output_path.iterdir())}")
    logger.info(f"\n🎉 FINE-TUNING SELESAI!")
    logger.info(f"   Best Val Accuracy: {best_val_accuracy*100:.2f}%")
    logger.info(f"   Test Accuracy:     {test_acc*100:.2f}%")
    
    return {
        "test_accuracy": test_acc,
        "test_loss": test_loss,
        "best_val_accuracy": best_val_accuracy,
        "classification_report": test_report,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune IndoBERT untuk klasifikasi sentimen Bahasa Indonesia"
    )
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL_NAME,
                        help="Nama base model dari HuggingFace")
    parser.add_argument("--output_dir", type=str, default=DEFAULT_OUTPUT_DIR,
                        help="Direktori output model")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS,
                        help="Jumlah epoch training")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="Ukuran batch")
    parser.add_argument("--lr", type=float, default=DEFAULT_LR,
                        help="Learning rate")
    parser.add_argument("--max_length", type=int, default=DEFAULT_MAX_LENGTH,
                        help="Panjang token maksimum")
    parser.add_argument("--kaggle_csv", type=str, default=None,
                        help="Path ke file CSV Kaggle Reviews (opsional)")
    
    args = parser.parse_args()
    
    results = train(args)
    
    # Verifikasi target akurasi (SM-02: ≥ 80%)
    if results["test_accuracy"] >= 0.80:
        logger.info(f"\n✅ Target akurasi ≥ 80% TERCAPAI: {results['test_accuracy']*100:.2f}%")
    else:
        logger.warning(f"\n⚠️ Target akurasi ≥ 80% BELUM TERCAPAI: {results['test_accuracy']*100:.2f}%")
        logger.info("Coba: tambah epoch, sesuaikan learning rate, atau tambah data training")


if __name__ == "__main__":
    main()
