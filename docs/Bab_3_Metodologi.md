# BAB 3: METODOLOGI PENELITIAN

## 3.1 Tahapan Penelitian
Penelitian ini menggunakan pendekatan rekayasa perangkat lunak (Software Engineering) berbasis siklus prototipe (Prototyping Model) yang terdiri dari lima tahapan utama:
1. **Analisis Kebutuhan Sistem:** Mengidentifikasi kebutuhan fungsional (scraping, inferensi model, UI interaktif) dan non-fungsional (performa <3 detik untuk dashboard awal, keamanan background thread).
2. **Pengumpulan Dataset & Pembangunan Model:** Persiapan dataset Dummy/Pre-Computed, eksperimen *fine-tuning* pada IndoBERT, serta konversi pipeline *HuggingFace Transformer* untuk mendukung klasifikasi polaritas 3 kelas.
3. **Desain Sistem & Arsitektur:** Perancangan topologi Microservices yang memisahkan beban antara Flask API dan Scraper API.
4. **Implementasi & Pengkodean:** Pembuatan antarmuka web, logika *Live Polling*, serta pengikatan model NLP (*inference engine*) dengan modul Scraper.
5. **Pengujian & Evaluasi:** Melakukan skenario uji *System Tests* (Network failure, text over-length) dan evaluasi performa model melalui matriks kebingungan (Confusion Matrix).

## 3.2 Arsitektur Sistem (System Context)
Sistem "Sentiments" menganut arsitektur *decoupled* yang asinkron guna mengatasi lambatnya jaringan web pada saat *scraping* teks. Berikut adalah diagram konteks integrasi antar layanan dalam ekosistem sistem.

```mermaid
flowchart LR
    User[User / Stakeholder]
    Flask(Flask Server\nUI & Orchestrator)
    FastAPI(FastAPI Server\nWeb Scraper Engine)
    Models[(IndoBERT\nWeights)]
    External((X / Portal Berita\nInternet))
    
    User -- "Kirim Topik / CSV" --> Flask
    Flask -- "Render Dashboard & Polling" --> User
    
    Flask -- "HTTP Request: /api/scrape\n(Asynchronous)" --> FastAPI
    FastAPI -- "HTTP Request" --> External
    External -- "Scraped HTML/JSON" --> FastAPI
    FastAPI -- "Parsed Text" --> Flask
    
    Flask -- "Load & Predict" --> Models
    Models -- "Sentimen (Pos/Neg/Net)" --> Flask
```

Pada desain di atas, *Flask* bertindak sebagai otak utama (Orchestrator) yang menangani sesi pengguna, antarmuka statis, serta melakukan inferensi model. Sedangkan *FastAPI* khusus menangani tugas Scraping yang didasarkan pada Playwright/BeautifulSoup tanpa memblokir server utama.

## 3.3 Alur Sekuensial Pipeline (Sequence Diagram)
Untuk mencegah peramban (*browser*) "membeku" saat memuat proses NLP dan komputasi yang berat, UI Frontend melakukan penarikan data secara berkala (AJAX Polling) setiap 2 detik ke titik henti `/api/status`.

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant F as Flask (app.py)
    participant B as Background Thread (pipeline.py)
    participant M as Inference Engine
    participant S as FastAPI (Scraper)

    U->>F: POST /api/start_pipeline (Topic)
    F->>B: Spawn Thread(start_scrape_pipeline)
    F-->>U: Return ReqID & Status: SCRAPING
    
    rect rgb(240, 248, 255)
        note right of B: Asynchronous Job
        B->>S: GET /scrape?topic=...
        S-->>B: Return list of Texts
        B->>B: Update Status (INFERENCING)
        B->>M: predict_batch(Texts)
        M-->>B: Return Predictions
        B->>B: Generate CSV & Update Status (COMPLETED)
    end
    
    loop Polling (setiap 2 detik)
        U->>F: GET /api/status?req_id=...
        F-->>U: Return Current Status (e.g., SCRAPING / INFERENCING)
    end
    
    U->>F: GET /api/status?req_id=...
    F-->>U: Return Status: COMPLETED + Data URL
    U->>F: GET /api/results (Data Dashboard)
    F-->>U: Return Final JSON Metrics
```

## 3.4 Desain Skema Data (ER Diagram)
Data hasil ekstraksi sentimen yang didapatkan dari *pipeline* disimpan pada berkas `.csv` statis sebagai basis data sementara (Caching System) untuk memotong waktu muat ulang dashboard di masa depan.

```mermaid
erDiagram
    DATASET_CSV {
        int id PK "Nomor identifikasi baris"
        string source "Sumber berita atau media sosial"
        string date "Tanggal ekstraksi teks"
        string title "Judul (opsional)"
        text text "Korpus teks opini/berita mentah"
        string clean_text "Teks setelah preprocessing NLP"
        string predicted_label "Positif, Negatif, atau Netral"
        float confidence_score "Peluang probabilitas model (0.0 - 1.0)"
        float inference_time_ms "Waktu kalkulasi untuk teks tersebut"
    }
```

## 3.5 Pra-pemrosesan Data (Preprocessing)
Model *Transformer* mengharuskan teks yang bersih untuk menghasilkan *embedding* vektor kata yang kuat. Modul pra-pemrosesan (`preprocessing.py`) melakukan pembersihan secara konsekutif:
1. **Case Folding & Cleaning**: Pengubahan karakter ke huruf kecil, penghapusan *username* (tag @), tagar (#), tautan (URL), karakter non-ASCII, dan tanda baca yang berlebihan.
2. **Normalisasi**: Transformasi kata-kata slang (bahasa gaul) maupun singkatan (seperti *yg*, *dgn*, *tdk*) menjadi ejaan baku Bahasa Indonesia (EYD) berdasarkan kamus (dictionary) yang dikonfigurasi pada sistem.
3. **Stopword Removal**: Menghapus kata hubung yang tidak membawa bobot sentimen (seperti *yang, dan, di, dari*).
4. **Tokenization (HuggingFace)**: Mengubah string teks ke dalam deret integer (Input IDs, Attention Mask) menggunakan `AutoTokenizer` dengan parameter *truncation* aktif yang memotong teks jika melebihi kuota memori (*MAX_TOKEN_LENGTH* = 512).

## 3.6 Transisi Antarmuka Frontend (State Machine)
Antarmuka Web (UI) dibangun sebagai *Single Page Application* tanpa framework tambahan (Vanilla JS). Transisi siklus hidup halaman dapat dimodelkan pada diagram status di bawah ini:

```mermaid
stateDiagram-v2
    [*] --> LandingPage : Load '/'
    
    LandingPage --> WaitRoom : Submit Form (Topic / File)
    
    state WaitRoom {
        [*] --> SCRAPING
        SCRAPING --> INFERENCING
        INFERENCING --> COMPLETED
        INFERENCING --> ERROR
        SCRAPING --> ERROR
    }
    
    WaitRoom --> Dashboard : Status == COMPLETED
    WaitRoom --> LandingPage : Status == ERROR (Show Alert)
    
    Dashboard --> LandingPage : Click "Analisis Topik Lain"
```
