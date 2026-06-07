# SentimenID — Sistem Klasifikasi Sentimen Teks Media Sosial Berbahasa Indonesia

> **Skripsi**: Klasifikasi Sentimen Teks Media Sosial Menggunakan IndoBERT dengan Strategi Multi-Domain  
> **Model**: `BertForSequenceClassification` (`indobert-base-p1`) · 3 Kelas: Positif, Negatif, Netral

---

## 📋 Daftar Isi
1. [Gambaran Umum](#gambaran-umum)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [Fitur Utama](#fitur-utama)
4. [Instalasi](#instalasi)
5. [Menjalankan Sistem](#menjalankan-sistem)
6. [Struktur Proyek](#struktur-proyek)
7. [Fine-Tuning Model](#fine-tuning-model)

---

## Gambaran Umum

Sistem ini mengklasifikasikan sentimen teks Bahasa Indonesia (dari media sosial, CSV, atau live scraping) menggunakan model **IndoBERT** yang telah di-*fine-tune* dengan strategi **Multi-Domain** — menggabungkan tiga dataset dari domain berbeda untuk meningkatkan robustisitas terhadap variasi bahasa (slang, *code-mixing*, bahasa formal).

**Kelas Sentimen:** 😊 Positif · 😞 Negatif · 😐 Netral

---

## Arsitektur Sistem

```
Pengguna (Browser)
     │
     ▼
Flask App (Port 5000)          ←→    FastAPI Scraper (Port 8000)
  - Analisis Tunggal                    - Playwright Browser
  - Batch CSV                           - Anti-Bot Evasion
  - Dashboard Visual                    - POST /scrape
  - IndoBERT Inference
```

---

## Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 🔍 **Analisis Tunggal** | Input teks → Label + Confidence Score instan |
| 📁 **Batch CSV** | Upload CSV → Proses massal → Download hasil |
| 🌐 **Live Scraping** | Cari tweet/konten web → Analisis real-time |
| 📊 **Dashboard** | Line Chart + Pie Chart + Word Cloud + Tabel |

---

## Instalasi

### Prasyarat
- Python 3.10+
- pip

### 1. Clone & Setup Virtual Environment

```powershell
git clone <repo-url>
cd sentimens
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependensi Flask App

```powershell
pip install -r requirements.txt
```

### 3. Install Dependensi Scraper

```powershell
pip install -r scraper/requirements.txt
playwright install chromium
```

### 4. Verifikasi Model

Pastikan folder `models/` berisi:
```
models/
├── config.json
├── model.safetensors
├── tokenizer.json
└── tokenizer_config.json
```

### 5. Konfigurasi Environment (opsional)

```powershell
copy .env.example .env
# Edit .env jika diperlukan
```

---

## Menjalankan Sistem

### Cara Cepat (Windows) — Jalankan Keduanya Sekaligus

```powershell
.\run_all.bat
```

Ini akan membuka **2 terminal**:
- Terminal 1: Flask App di `http://localhost:5000`
- Terminal 2: FastAPI Scraper di `http://localhost:8000`

### Cara Manual (Terpisah)

**Terminal 1 — Flask App:**
```powershell
python app.py
```

**Terminal 2 — FastAPI Scraper:**
```powershell
cd scraper
python main.py
```

### Akses Aplikasi

| URL | Deskripsi |
|-----|-----------|
| http://localhost:5000 | Halaman utama Flask |
| http://localhost:5000/batch | Upload CSV |
| http://localhost:5000/scrape | Live Scraping |
| http://localhost:5000/dashboard | Dashboard Visual |
| http://localhost:8000/docs | Dokumentasi FastAPI Scraper |
| http://localhost:8000/health | Health check scraper |

---

## Struktur Proyek

```
sentimens/
├── app.py                  # Flask main application (Port 5000)
├── config.py               # Konfigurasi sistem
├── preprocessing.py        # Modul praproses teks
├── inference.py            # Modul inferensi IndoBERT
├── utils.py                # Helper functions
├── requirements.txt        # Dependensi Flask
├── run_all.bat             # Script launcher Windows
│
├── models/                 # Model fine-tuned (tidak di-commit ke git)
│   ├── config.json
│   ├── model.safetensors
│   ├── tokenizer.json
│   └── tokenizer_config.json
│
├── scraper/                # FastAPI Scraper Microservice (Port 8000)
│   ├── main.py             # FastAPI application
│   ├── scraper.py          # Playwright scraping engine
│   └── requirements.txt
│
├── training/               # Script fine-tuning & evaluasi
│   ├── data_loader.py      # Loader dataset multi-domain
│   ├── train.py            # Script fine-tuning IndoBERT
│   └── evaluate.py         # Script evaluasi model
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── result_single.html
│   ├── batch.html
│   ├── result_batch.html
│   ├── scrape.html
│   ├── result_scrape.html
│   ├── dashboard.html
│   └── error.html
│
└── static/
    └── css/
        └── style.css       # Custom dark theme CSS
```

---

## Fine-Tuning Model

Jika ingin melatih ulang model dari awal:

### 1. Siapkan Dataset

Dataset otomatis diunduh dari HuggingFace:
- `indonlp/indonlu` (SmSA)
- `indonlp/NusaX-senti`

Dataset Kaggle: taruh di `training/data/kaggle_reviews.csv`

### 2. Jalankan Training

```powershell
cd training
python train.py --epochs 3 --batch_size 16 --lr 2e-5
```

### 3. Evaluasi Model

```powershell
python evaluate.py --model_path ../models --use_auto_split
```

---

## Praproses Teks

Pipeline praproses (sebelum inferensi IndoBERT):

1. Hapus URL (`http://`, `www.`)
2. Hapus @mention
3. Hapus simbol `#` (kata dipertahankan)
4. Hapus karakter non-alfanumerik
5. Case folding (→ lowercase)
6. Normalisasi spasi

> ℹ️ **Catatan**: Stopword *tidak* dihapus karena IndoBERT memanfaatkan konteks kalimat penuh.

---

## Target Kinerja (Success Metrics)

| Metrik | Target | Keterangan |
|--------|--------|-----------|
| Akurasi Model | ≥ 80% | SM-02 |
| Latensi Analisis Tunggal | ≤ 5 detik | SM-03 |
| Batch CSV (100+ baris) | ✅ Berfungsi | SM-04 |
| Live Scraping (≥ 20 data) | ✅ Berfungsi | SM-05 |
| Dashboard 4 Komponen | ✅ Render | SM-06 |
| 2 Server Bersamaan | ✅ Port 5000 + 8000 | SM-07 |

---

*© 2025 — Dokumen Skripsi Sistem Klasifikasi Sentimen IndoBERT*
