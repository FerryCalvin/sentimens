# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Sistem Klasifikasi Sentimen Teks Media Sosial Menggunakan IndoBERT dengan Strategi Multi-Domain

---

| Atribut Dokumen     | Detail                                                                 |
|---------------------|------------------------------------------------------------------------|
| **Versi Dokumen**   | v1.0.0                                                                 |
| **Status**          | Final Draft – Siap Uji Sidang                                          |
| **Tanggal**         | Juni 2025                                                              |
| **Peran Penyusun**  | Senior Product Manager & System Architect                              |
| **Metodologi**      | Agile/Scrum (disesuaikan untuk konteks penelitian akademik)            |
| **Audiens**         | Dosen Penguji Skripsi, Tim Pengembang Perangkat Lunak                  |

---

## DAFTAR ISI

1. [Product Overview](#1-product-overview)
2. [System Architecture](#2-system-architecture)
3. [User Flow & Epics](#3-user-flow--epics)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Data Flow & AI Pipeline](#6-data-flow--ai-pipeline)
7. [Success Metrics & Acceptance Criteria](#7-success-metrics--acceptance-criteria)
8. [Glossarium & Referensi](#8-glossarium--referensi)

---

## 1. PRODUCT OVERVIEW

### 1.1 Pernyataan Masalah *(Problem Statement)*

Ledakan volume informasi di platform media sosial, khususnya X (sebelumnya Twitter), telah menciptakan fenomena **information overload** yang menyulitkan individu, akademisi, maupun pelaku industri dalam memaknai opini publik secara efisien. Bahasa Indonesia yang digunakan di media sosial bersifat sangat heterogen: mencakup bahasa formal, slang (*bahasa gaul*), campur kode (*code-mixing*) antara bahasa Indonesia dan bahasa Inggris, serta penggunaan singkatan dan emotikon. Pendekatan berbasis leksikon maupun model Machine Learning konvensional terbukti tidak cukup robust dalam menghadapi variasi linguistik tersebut.

Tidak tersedianya alat analisis sentimen berbasis Bahasa Indonesia yang mudah diakses, akurat, dan dapat memproses data secara *live* dari platform media sosial menjadi celah signifikan yang perlu diisi melalui penelitian terapan ini.

### 1.2 Visi Produk *(Product Vision)*

> **"Menjadi platform analitik sentimen Bahasa Indonesia yang terpercaya, akurat, dan mudah diakses; memungkinkan siapapun untuk memahami lanskap opini publik di media sosial secara cepat dan berbasis data."**

### 1.3 Misi Produk *(Product Mission)*

Sistem ini dibangun dengan misi untuk:

- **Mendemokratisasi** analisis teks berbahasa Indonesia dengan menyediakan antarmuka yang intuitif tanpa memerlukan keahlian pemrograman dari pengguna akhir.
- **Mengatasi keterbatasan** model monodomain dengan menerapkan strategi fine-tuning multi-domain pada IndoBERT, sehingga sistem mampu menangani ragam bahasa media sosial yang kompleks.
- **Mempercepat** proses pemantauan isu publik melalui fitur *live scraping* yang terintegrasi langsung dengan platform X (Twitter).
- **Menyajikan** hasil analisis dalam format visual yang informatif dan dapat ditindaklanjuti.

### 1.4 Target Audiens *(Target Audience)*

| Segmen Pengguna          | Deskripsi                                                                                      | Kebutuhan Utama                                       |
|--------------------------|-----------------------------------------------------------------------------------------------|-------------------------------------------------------|
| **Peneliti & Akademisi** | Mahasiswa, dosen, dan peneliti yang memerlukan analisis opini publik berbasis teks            | Analisis batch CSV, ekspor hasil, akurasi tinggi      |
| **Analis Komunikasi**    | Praktisi hubungan masyarakat (humas), tim media monitoring instansi publik/swasta             | Pemantauan isu terkini via keyword, dashboard visual  |
| **Pengembang Perangkat Lunak** | Engineer yang tertarik mengintegrasikan atau memahami arsitektur sistem ini              | Dokumentasi API, arsitektur microservices yang jelas  |
| **Dosen Penguji Skripsi** | Akademisi penguji yang mengevaluasi validitas riset dan kualitas implementasi sistem        | Akurasi model, kelengkapan fitur, bukti fungsionalitas|

### 1.5 Ruang Lingkup Produk *(Product Scope)*

#### Dalam Lingkup *(In-Scope)*
- Klasifikasi sentimen tiga kelas: **Positif, Negatif, dan Netral**.
- Analisis teks tunggal secara sinkronus.
- Analisis batch melalui unggahan berkas CSV.
- *Live scraping* teks dari platform X (Twitter) berdasarkan kata kunci.
- Visualisasi hasil analisis dalam bentuk *line chart*, *pie chart*, *word cloud*, dan tabel data mentah.
- Praproses teks otomatis (*cleansing* dan *case folding*).

#### Di Luar Lingkup *(Out-of-Scope)*
- Analisis sentimen untuk bahasa selain Bahasa Indonesia (dan campur kode Indonesia-Inggris).
- Scraping dari platform media sosial lain (Instagram, Facebook, TikTok) pada versi ini.
- Sistem otentikasi pengguna dan manajemen akun (*user management*).
- Penyimpanan data historis ke *database* persisten (semua pemrosesan bersifat *stateless* per sesi).
- Deployment ke lingkungan *cloud* berskala produksi (sistem ini dirancang untuk demonstrasi dan penelitian).

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Paradigma Arsitektur

Sistem dirancang menggunakan paradigma **Microservices** yang disederhanakan, memisahkan tanggung jawab antara komponen utama aplikasi web dengan komponen khusus pengambilan data (*scraping*). Pemisahan ini mengikuti prinsip **Separation of Concerns** dan **Single Responsibility Principle**, sehingga tiap layanan dapat dikembangkan, diuji, dan dipelihara secara independen.

### 2.2 Diagram Arsitektur Tekstual *(High-Level Architecture)*

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         LAPISAN KLIEN (CLIENT LAYER)                        ║
║                                                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐   ║
║   │                      BROWSER PENGGUNA                               │   ║
║   │   [Antarmuka Web: HTML5 + Jinja2 Template + Bootstrap 5 + JS]       │   ║
║   │                                                                     │   ║
║   │   ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐    │   ║
║   │   │ Form Input  │  │  Upload CSV  │  │  Search Keyword Form   │    │   ║
║   │   │  (Single)   │  │   (Batch)    │  │   (Live Scraping)      │    │   ║
║   │   └──────┬──────┘  └──────┬───────┘  └───────────┬────────────┘    │   ║
║   │          │                │                       │                 │   ║
║   │          └────────────────┴───────────────────────┘                 │   ║
║   │                           │ HTTP Request (GET/POST)                 │   ║
║   └───────────────────────────┼─────────────────────────────────────────┘   ║
╚═══════════════════════════════╪═════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║              LAPISAN APLIKASI UTAMA (MAIN APPLICATION LAYER)                ║
║              Port: 5000 | Runtime: Python 3.10+                              ║
║                                                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐   ║
║   │                   FLASK MAIN APPLICATION SERVER                     │   ║
║   │                                                                     │   ║
║   │  ┌──────────────────┐    ┌──────────────────────────────────────┐   │   ║
║   │  │  Route Handler   │    │        AI Inference Engine           │   │   ║
║   │  │ /analyze         │    │  ┌────────────────────────────────┐  │   │   ║
║   │  │ /batch           │───►│  │     IndoBERT Model             │  │   │   ║
║   │  │ /scrape          │    │  │  (pytorch_model.bin – di RAM)  │  │   │   ║
║   │  │ /dashboard       │    │  │                                │  │   │   ║
║   │  └──────────────────┘    │  │  Tokenizer: WordPiece          │  │   │   ║
║   │                          │  │  Output: Softmax (3 kelas)     │  │   │   ║
║   │  ┌──────────────────┐    │  └────────────────────────────────┘  │   │   ║
║   │  │ Text Preprocessor│    └──────────────────────────────────────┘   │   ║
║   │  │ - Cleansing      │                                               │   ║
║   │  │ - Case Folding   │    ┌──────────────────────────────────────┐   │   ║
║   │  │ - Tokenization   │    │       HTTP Client (httpx/requests)   │   │   ║
║   │  └──────────────────┘    │  Memanggil FastAPI Scraper Service   │   │   ║
║   │                          └──────────────────────────────────────┘   │   ║
║   └──────────────────────────────────────────┬──────────────────────────┘   ║
╚════════════════════════════════════════════════╪════════════════════════════╝
                                                 │
                              HTTP Request        │ (Internal API Call)
                              POST /scrape        │ Payload: {"keyword": "..."}
                              ke Port 8000        │
                                                 ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║             LAPISAN SCRAPER (MICROSERVICE / SCRAPER LAYER)                   ║
║             Port: 8000 | Runtime: Python 3.10+ | Framework: FastAPI          ║
║                                                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐   ║
║   │                   FASTAPI SCRAPER SERVICE                           │   ║
║   │                                                                     │   ║
║   │  ┌──────────────────────────────────────────────────────────────┐  │   ║
║   │  │                  Async Scraping Engine                        │  │   ║
║   │  │                                                              │  │   ║
║   │  │  ┌────────────────────┐    ┌───────────────────────────┐    │  │   ║
║   │  │  │  Playwright Engine │    │  TLS Fingerprint Manager  │    │  │   ║
║   │  │  │  (Chromium/async)  │    │  (Anti-Bot Evasion)       │    │  │   ║
║   │  │  └────────────────────┘    └───────────────────────────┘    │  │   ║
║   │  │                                                              │  │   ║
║   │  │  Endpoint: POST /scrape                                      │  │   ║
║   │  │  Input:    { "keyword": str, "limit": int }                  │  │   ║
║   │  │  Output:   { "data": [{"text": str, "date": str}, ...] }     │  │   ║
║   │  └──────────────────────────────────────────────────────────────┘  │   ║
║   └─────────────────────────────────────────────────────────────────────┘   ║
║                                      │                                       ║
║                                      ▼                                       ║
║                        ┌─────────────────────────┐                          ║
║                        │  Platform X (Twitter)   │                          ║
║                        │  (External Data Source) │                          ║
║                        └─────────────────────────┘                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 2.3 Penjelasan Komponen Arsitektur

#### Komponen 1: Browser Pengguna (Client Layer)
Antarmuka pengguna dirender di sisi klien menggunakan **HTML5** dengan **template engine Jinja2** yang disuntikkan oleh Flask. Kerangka tampilan menggunakan **Bootstrap 5** untuk responsivitas, sementara interaktivitas dinamis (seperti pembaruan progres bar atau render grafik) ditangani oleh **JavaScript vanilla** dan pustaka **Chart.js** serta **WordCloud2.js**.

#### Komponen 2: Flask Main Application Server (Port 5000)
Merupakan inti dari sistem, bertanggung jawab atas:
- **Routing & View Rendering**: Mengelola semua endpoint HTTP dan merender halaman HTML melalui Jinja2.
- **State Management**: Mengelola data sesi pengguna (*per-request stateless*).
- **AI Inference Engine**: Memuat model IndoBERT (*fine-tuned*) beserta tokenizer-nya ke dalam RAM pada saat *startup* aplikasi. Inferensi dijalankan secara sinkronus menggunakan **PyTorch**.
- **Text Preprocessor**: Modul praproses teks yang berjalan sebelum setiap inferensi.
- **Orchestrator**: Bertindak sebagai orkestrator yang memanggil layanan FastAPI dan kemudian memproses hasilnya dengan model AI.

#### Komponen 3: FastAPI Scraper Service (Port 8000)
Merupakan *microservice* khusus yang berjalan secara independen, bertanggung jawab atas:
- **Asynchronous Scraping**: Menggunakan **Playwright** dalam mode asinkronus (`asyncio`) untuk mengontrol browser Chromium tanpa antarmuka grafis (*headless*) guna mengambil konten dari platform X.
- **Anti-Bot Evasion (TLS Fingerprinting)**: Menerapkan teknik modifikasi *TLS Client Hello fingerprint* untuk meminimalkan kemungkinan pemblokiran oleh sistem deteksi bot platform target.
- **Data Serialization**: Mengembalikan data yang telah diekstrak dalam format JSON terstruktur.

### 2.4 Alur Interaksi Antar Komponen *(Sequence Flow)*

```
Pengguna      Flask App (Port 5000)      FastAPI Scraper (Port 8000)    Platform X
    │                  │                           │                        │
    │──[POST /scrape]─►│                           │                        │
    │  {keyword: "..."}│                           │                        │
    │                  │──[POST /scrape]───────────►│                       │
    │                  │  {keyword, limit}          │                        │
    │                  │                           │──[Browser.launch()]───►│
    │                  │                           │  [Playwright Headless]  │
    │                  │                           │◄──[HTML/JSON Response]──│
    │                  │                           │  [Parse Tweet Data]     │
    │                  │◄──[200 OK: JSON Data]─────│                        │
    │                  │  [{text, date}, ...]       │                        │
    │                  │                           │                        │
    │                  │──[Preprocessor]──┐        │                        │
    │                  │  Cleansing       │        │                        │
    │                  │  Case Folding    │        │                        │
    │                  │  Tokenization    │        │                        │
    │                  │◄─────────────────┘        │                        │
    │                  │                           │                        │
    │                  │──[IndoBERT Inference]──┐  │                        │
    │                  │  forward(input_ids)     │  │                        │
    │                  │  softmax(logits)        │  │                        │
    │                  │◄───────────────────────┘  │                        │
    │                  │                           │                        │
    │◄──[Render Dashboard]                         │                        │
    │  [Chart, Tabel, WordCloud]                   │                        │
```

---

## 3. USER FLOW & EPICS

### 3.1 Peta Epik *(Epic Map)*

Seluruh fungsionalitas sistem diorganisasikan ke dalam **4 Epik** berikut:

| Kode Epik | Nama Epik                       | Prioritas | Sprint Target |
|-----------|---------------------------------|-----------|---------------|
| **EP-01** | Analisis Teks Tunggal           | Tinggi    | Sprint 1      |
| **EP-02** | Analisis Batch via CSV          | Tinggi    | Sprint 2      |
| **EP-03** | Pencarian Isu Terkini (Scraping)| Tinggi    | Sprint 2-3    |
| **EP-04** | Dashboard Visualisasi Data      | Sedang    | Sprint 3      |

---

### 3.2 Epik 1: Analisis Teks Tunggal (EP-01)

**Deskripsi Epik**: Sebagai pengguna, saya ingin dapat memasukkan satu kalimat teks dan mendapatkan hasil klasifikasi sentimen secara instan.

#### User Stories

| Kode    | User Story                                                                                                                                 | Kriteria Penerimaan *(Acceptance Criteria)*                                                                                                               | Poin |
|---------|--------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| US-01.1 | **Sebagai** pengguna, **saya ingin** mengisi formulir teks tunggal di halaman utama, **agar** saya dapat menganalisis sentimen satu kalimat. | - Terdapat `<textarea>` dengan placeholder yang jelas. <br>- Tombol "Analisis" tersedia dan aktif. <br>- Validasi: input tidak boleh kosong.               | 3    |
| US-01.2 | **Sebagai** pengguna, **saya ingin** melihat teks yang telah dibersihkan (*cleaned text*), **agar** saya memahami apa yang dianalisis model. | - Sistem menampilkan teks asli dan teks setelah praproses. <br>- Perubahan karakter/URL terlihat jelas.                                                   | 2    |
| US-01.3 | **Sebagai** pengguna, **saya ingin** melihat label sentimen (Positif/Negatif/Netral) dengan persentase keyakinan (*confidence score*), **agar** saya tahu seberapa yakin model. | - Label sentimen ditampilkan dengan warna kode (hijau/merah/abu). <br>- Persentase tiga kelas ditampilkan (total ≈ 100%). <br>- Waktu inferensi ditampilkan. | 3    |
| US-01.4 | **Sebagai** pengguna, **saya ingin** mendapatkan umpan balik ketika teks saya terlalu pendek atau mengandung karakter tidak valid, **agar** saya dapat memperbaiki input. | - Pesan error muncul di bawah formulir. <br>- Formulir tidak di-submit jika validasi gagal.                                                               | 2    |

#### Acceptance Criteria Epik (Definition of Done)
- Semua 4 User Story berhasil diimplementasikan dan diuji.
- Latensi respons analisis teks tunggal ≤ 3 detik pada hardware spesifikasi minimum.
- Tidak terdapat *crash* atau *unhandled exception* pada 20 pengujian berturut-turut.

---

### 3.3 Epik 2: Analisis Batch via CSV (EP-02)

**Deskripsi Epik**: Sebagai peneliti, saya ingin mengunggah berkas CSV berisi ratusan atau ribuan teks sekaligus dan mendapatkan hasil klasifikasi secara massal.

#### User Stories

| Kode    | User Story                                                                                                                                          | Kriteria Penerimaan *(Acceptance Criteria)*                                                                                                                   | Poin |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| US-02.1 | **Sebagai** peneliti, **saya ingin** mengunggah berkas CSV dengan satu kolom teks, **agar** saya dapat memproses banyak data sekaligus.               | - Tersedia komponen *file upload* yang menerima ekstensi `.csv`. <br>- Validasi format kolom: sistem mendeteksi kolom teks secara otomatis atau meminta konfirmasi. | 5    |
| US-02.2 | **Sebagai** peneliti, **saya ingin** melihat progress pemrosesan batch, **agar** saya tahu estimasi waktu selesai.                                   | - Terdapat *progress indicator* (persentase atau progress bar). <br>- Jumlah data yang sudah diproses ditampilkan.                                             | 3    |
| US-02.3 | **Sebagai** peneliti, **saya ingin** mengunduh hasil analisis dalam format CSV, **agar** saya dapat menggunakannya untuk analisis lanjutan.           | - Tombol "Unduh Hasil" tersedia setelah pemrosesan selesai. <br>- Berkas CSV keluaran memiliki kolom: `teks_asli`, `teks_bersih`, `sentimen`, `confidence_pos`, `confidence_neg`, `confidence_net`. | 5    |
| US-02.4 | **Sebagai** peneliti, **saya ingin** melihat ringkasan statistik hasil batch (total, komposisi sentimen), **agar** saya dapat langsung memahami hasil secara keseluruhan. | - Setelah pemrosesan, tampil ringkasan: total data, jumlah per kelas, persentase tiap kelas.                                                                  | 3    |

#### Acceptance Criteria Epik (Definition of Done)
- Sistem dapat memproses berkas CSV berisi minimal 1.000 baris tanpa *crash*.
- Throughput pemrosesan ≥ 5 teks/detik pada CPU standar (tanpa GPU).
- Berkas CSV hasil unduhan terbuka dengan benar di Microsoft Excel dan Google Sheets.

---

### 3.4 Epik 3: Pencarian Isu Terkini / Live Scraping (EP-03)

**Deskripsi Epik**: Sebagai analis, saya ingin mencari tweet terkini berdasarkan kata kunci dan mendapatkan analisis sentimennya secara langsung.

#### User Stories

| Kode    | User Story                                                                                                                                           | Kriteria Penerimaan *(Acceptance Criteria)*                                                                                                                          | Poin |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| US-03.1 | **Sebagai** analis, **saya ingin** memasukkan satu atau beberapa kata kunci, **agar** sistem dapat mencari tweet yang relevan.                        | - Formulir pencarian tersedia dengan input kata kunci dan pilihan jumlah tweet (misal: 50, 100, 200). <br>- Tombol "Cari & Analisis" tersedia.                         | 3    |
| US-03.2 | **Sebagai** analis, **saya ingin** melihat indikator loading selama proses scraping berlangsung, **agar** saya tidak mengira sistem *freeze*.          | - Terdapat animasi *loading spinner* atau pesan status ("Sedang mengambil data...", "Sedang menganalisis..."). <br>- Waktu tunggu maksimum 60 detik sebelum *timeout*. | 3    |
| US-03.3 | **Sebagai** analis, **saya ingin** melihat hasil scraping berupa tabel tweet yang telah diklasifikasi sentimennya, **agar** saya dapat menelusuri data mentah. | - Tabel menampilkan kolom: Teks Tweet, Tanggal, Sentimen, Confidence. <br>- Tabel mendukung pengurutan (*sortable*) berdasarkan tanggal dan sentimen.               | 5    |
| US-03.4 | **Sebagai** analis, **saya ingin** melihat distribusi sentimen dari hasil scraping secara visual, **agar** saya dapat langsung mendapatkan gambaran besar. | - Setelah scraping selesai, pengguna diarahkan ke halaman Dashboard Visualisasi secara otomatis.                                                                      | 3    |

#### Acceptance Criteria Epik (Definition of Done)
- Sistem berhasil mengambil setidaknya 50 tweet untuk kata kunci umum dalam waktu ≤ 60 detik.
- Data tweet yang dikembalikan memiliki minimal dua atribut: `teks` dan `tanggal`.
- Sistem tidak mengekspos error internal ke antarmuka pengguna saat scraping gagal; sebaliknya, menampilkan pesan ramah.

---

### 3.5 Epik 4: Dashboard Visualisasi Data (EP-04)

**Deskripsi Epik**: Sebagai pengguna, saya ingin melihat hasil analisis sentimen dalam format visual yang informatif dan interaktif.

#### User Stories

| Kode    | User Story                                                                                                                                            | Kriteria Penerimaan *(Acceptance Criteria)*                                                                                                                         | Poin |
|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| US-04.1 | **Sebagai** pengguna, **saya ingin** melihat *line chart* tren sentimen berdasarkan waktu, **agar** saya memahami dinamika pergerakan opini publik.     | - Sumbu X menampilkan waktu (tanggal/jam). <br>- Sumbu Y menampilkan jumlah atau proporsi tiap sentimen. <br>- Tiga garis berbeda warna (Positif, Negatif, Netral). | 5    |
| US-04.2 | **Sebagai** pengguna, **saya ingin** melihat *pie chart* komposisi sentimen, **agar** saya mengetahui proporsi keseluruhan secara sekilas.              | - Tiga segmen dengan label persentase. <br>- Legenda warna yang konsisten dengan komponen lain.                                                                      | 3    |
| US-04.3 | **Sebagai** pengguna, **saya ingin** melihat *word cloud* dari teks yang dianalisis, **agar** saya mengetahui kata-kata yang paling sering muncul.      | - *Word cloud* dirender secara dinamis dari teks hasil praproses. <br>- Kata yang lebih sering muncul ditampilkan lebih besar. <br>- Minimal 30 kata ditampilkan.   | 5    |
| US-04.4 | **Sebagai** pengguna, **saya ingin** melihat tabel data mentah (*raw data table*) dari semua teks yang dianalisis, **agar** saya dapat memeriksa hasil secara detail. | - Tabel menampilkan semua baris hasil analisis. <br>- Tabel mendukung paginasi (≤ 25 baris per halaman). <br>- Tabel mendukung pencarian (*search filter*).         | 3    |

#### Acceptance Criteria Epik (Definition of Done)
- Semua 4 komponen visual (line chart, pie chart, word cloud, tabel) ter-render dengan benar.
- Dashboard responsif dan dapat ditampilkan di resolusi layar minimum 1280×720 piksel.
- Semua grafik ter-render dalam waktu ≤ 2 detik setelah data tersedia.

---

## 4. FUNCTIONAL REQUIREMENTS

### 4.1 Modul Praproses Teks *(Text Preprocessing Module)*

**FR-PP-01 – URL Removal**: Sistem HARUS menghapus semua URL (dimulai dengan `http://`, `https://`, atau `www.`) dari teks input sebelum analisis.

**FR-PP-02 – Mention & Hashtag Removal**: Sistem HARUS menghapus mention pengguna (`@username`) dan tanda hashtag (`#`) dari teks (simbol `#` dihapus, namun kata di belakangnya dipertahankan).

**FR-PP-03 – Karakter Khusus & Angka**: Sistem HARUS menghapus karakter non-alfanumerik kecuali spasi. Angka boleh dipertahankan atau dihapus berdasarkan konfigurasi.

**FR-PP-04 – Case Folding**: Sistem HARUS mengubah seluruh teks menjadi huruf kecil (*lowercase*).

**FR-PP-05 – Whitespace Normalization**: Sistem HARUS menghapus spasi berlebih (lebih dari satu spasi berurutan) dan *leading/trailing whitespace*.

**FR-PP-06 – Tanpa *Stopword Removal***: Sistem TIDAK BOLEH melakukan penghapusan *stopword*. Keputusan desain ini diambil karena model IndoBERT memanfaatkan konteks penuh kalimat, dan penghapusan *stopword* berpotensi merusak konteks linguistik.

**FR-PP-07 – WordPiece Tokenization**: Sistem HARUS menggunakan tokenizer resmi IndoBERT (`indobenchmark/indobert-base-p1`) untuk mengonversi teks menjadi token ID dan attention mask.

**FR-PP-08 – Truncation & Padding**: Sistem HARUS menerapkan *truncation* pada teks yang melebihi 512 token dan *padding* pada teks yang lebih pendek, sesuai standar input model BERT.

---

### 4.2 Modul Inferensi AI *(AI Inference Module)*

**FR-AI-01 – Model Loading**: Sistem HARUS memuat model `pytorch_model.bin` beserta `config.json` dan `tokenizer_config.json` ke memori RAM pada saat *startup* aplikasi Flask (`app.py`), bukan pada setiap permintaan masuk.

**FR-AI-02 – Mode Inferensi**: Inferensi model HARUS dijalankan dalam mode `torch.no_grad()` untuk menonaktifkan komputasi gradien, mengoptimalkan penggunaan memori dan kecepatan.

**FR-AI-03 – Output Probabilitas**: Model HARUS menghasilkan probabilitas untuk tiga kelas (Negatif, Netral, Positif) menggunakan fungsi *softmax* pada lapisan logits terakhir.

**FR-AI-04 – Label Prediksi**: Sistem HARUS mengambil kelas dengan probabilitas tertinggi sebagai label prediksi akhir (`argmax`).

**FR-AI-05 – Format Output**: Modul inferensi HARUS mengembalikan objek terstruktur yang memuat: `predicted_label` (string), `confidence_positive` (float), `confidence_negative` (float), `confidence_neutral` (float).

---

### 4.3 Modul Analisis Teks Tunggal

**FR-ST-01 – Endpoint**: Flask HARUS menyediakan endpoint `POST /analyze` yang menerima parameter `text` dalam request body.

**FR-ST-02 – Alur Pemrosesan**: Sistem HARUS menjalankan alur: Input → Praproses → Tokenisasi → Inferensi → Render Hasil.

**FR-ST-03 – Tampilan Hasil**: Halaman hasil HARUS menampilkan: (a) Teks asli, (b) Teks setelah praproses, (c) Label sentimen, (d) Persentase keyakinan untuk ketiga kelas, (e) Waktu inferensi dalam milidetik.

---

### 4.4 Modul Analisis Batch/CSV

**FR-BT-01 – Endpoint**: Flask HARUS menyediakan endpoint `POST /batch` yang menerima unggahan berkas CSV melalui `multipart/form-data`.

**FR-BT-02 – Validasi Berkas**: Sistem HARUS memvalidasi bahwa (a) ekstensi berkas adalah `.csv`, (b) berkas tidak kosong, (c) berkas memiliki minimal satu kolom yang dapat diinterpretasikan sebagai teks.

**FR-BT-03 – Pemrosesan Iteratif**: Sistem HARUS memproses setiap baris CSV secara iteratif, menerapkan praproses dan inferensi pada setiap teks.

**FR-BT-04 – Penanganan Baris Kosong**: Sistem HARUS melewati (*skip*) baris yang kosong atau hanya mengandung spasi, dan mencatatnya sebagai "data tidak valid" pada ringkasan.

**FR-BT-05 – Output CSV**: Berkas CSV hasil unduhan HARUS memiliki kolom-kolom berikut dalam urutan yang ditetapkan:

```
teks_asli | teks_bersih | sentimen | confidence_positif | confidence_negatif | confidence_netral
```

**FR-BT-06 – Ringkasan Statistik**: Setelah pemrosesan, sistem HARUS menampilkan ringkasan yang memuat: total baris diproses, jumlah dan persentase per kelas sentimen, jumlah baris tidak valid.

---

### 4.5 Modul Live Scraping (FastAPI Service)

**FR-SC-01 – Endpoint FastAPI**: FastAPI HARUS menyediakan endpoint `POST /scrape` yang menerima JSON body: `{"keyword": string, "limit": integer}`.

**FR-SC-02 – Respons FastAPI**: Endpoint HARUS mengembalikan JSON dengan format: `{"status": "success", "data": [{"text": string, "date": string (ISO 8601)}, ...], "count": integer}`.

**FR-SC-03 – Asynchronous Execution**: Scraping HARUS dijalankan secara asinkronus menggunakan `asyncio` dan `playwright.async_api` agar tidak memblokir event loop FastAPI.

**FR-SC-04 – TLS Fingerprinting Evasion**: Servis HARUS mengimplementasikan teknik modifikasi *TLS Client Hello* (misalnya melalui pustaka `curl_cffi` atau konfigurasi Playwright dengan *custom browser args*) untuk meminimalkan deteksi sebagai bot otomatis.

**FR-SC-05 – Penanganan Rate Limit**: Servis HARUS mengimplementasikan penundaan (*delay*) acak antara permintaan halaman (0.5 – 2.5 detik) untuk meniru perilaku pengguna manusia.

**FR-SC-06 – Timeout Konfigurasi**: Servis HARUS memiliki batas waktu (*timeout*) permintaan yang dapat dikonfigurasi (default: 45 detik).

**FR-SC-07 – Pemanggilan dari Flask**: Flask HARUS memanggil FastAPI menggunakan library HTTP (`httpx` atau `requests`) dengan timeout 60 detik dan menangani kemungkinan kegagalan koneksi dengan *fallback error message*.

---

### 4.6 Modul Dashboard Visualisasi

**FR-VZ-01 – Line Chart (Tren Waktu)**: Sistem HARUS merender *line chart* menggunakan Chart.js yang menampilkan distribusi sentimen per satuan waktu (per jam/per hari, bergantung rentang data).

**FR-VZ-02 – Pie Chart (Komposisi)**: Sistem HARUS merender *pie chart* (atau *doughnut chart*) yang menampilkan proporsi ketiga kelas sentimen dalam persen.

**FR-VZ-03 – Word Cloud**: Sistem HARUS merender *word cloud* dari kata-kata yang diekstrak dari semua teks bersih yang dianalisis, menggunakan pustaka WordCloud2.js atau equivalen.

**FR-VZ-04 – Raw Data Table**: Sistem HARUS merender tabel data yang dapat dipaginasi (25 baris/halaman) dan memiliki fitur pencarian inline.

**FR-VZ-05 – Konsistensi Warna**: Semua komponen visual HARUS menggunakan skema warna yang konsisten: Positif = Hijau (`#28a745`), Negatif = Merah (`#dc3545`), Netral = Abu-abu (`#6c757d`).

---

## 5. NON-FUNCTIONAL REQUIREMENTS

### 5.1 Persyaratan Kinerja *(Performance Requirements)*

| ID       | Persyaratan                                                                                      | Metrik Target                                    |
|----------|--------------------------------------------------------------------------------------------------|--------------------------------------------------|
| NFR-P-01 | Latensi analisis teks tunggal                                                                    | ≤ 3 detik (CPU standar, tanpa GPU)               |
| NFR-P-02 | Throughput analisis batch                                                                        | ≥ 5 teks/detik                                   |
| NFR-P-03 | Waktu respons scraping (termasuk network latency ke X)                                          | ≤ 60 detik untuk 100 tweet                       |
| NFR-P-04 | Waktu render dashboard (setelah data tersedia)                                                   | ≤ 2 detik                                        |
| NFR-P-05 | Ukuran berkas model di RAM                                                                       | ≤ 1.5 GB (model IndoBERT-base)                   |
| NFR-P-06 | Waktu startup aplikasi Flask (termasuk loading model)                                            | ≤ 30 detik pada *cold start*                     |

### 5.2 Persyaratan Keamanan *(Security Requirements)*

| ID       | Persyaratan                                                                                      | Detail Implementasi                                                  |
|----------|--------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| NFR-S-01 | TLS Fingerprinting untuk Scraping                                                                | Memodifikasi *TLS Client Hello* agar tidak teridentifikasi sebagai Python/requests default. Menggunakan JA3/JA3S fingerprint yang menyerupai browser nyata. |
| NFR-S-02 | Validasi Input Pengguna                                                                          | Semua input dari formulir HARUS di-*sanitize* untuk mencegah injeksi HTML/JS (*XSS*). Flask HARUS menggunakan `markupsafe.escape()` pada teks input. |
| NFR-S-03 | Pembatasan Ukuran Berkas Unggahan                                                                | Berkas CSV yang diunggah dibatasi maksimum **16 MB** (dikonfigurasi melalui `MAX_CONTENT_LENGTH` Flask). |
| NFR-S-04 | Pembatasan Akses Antarmuka Scraper                                                               | Endpoint FastAPI (Port 8000) TIDAK BOLEH diekspos langsung ke publik. Akses HANYA diizinkan dari alamat IP lokal (`localhost`/`127.0.0.1`) atau jaringan internal. |
| NFR-S-05 | Penanganan Error Aman                                                                             | Sistem TIDAK BOLEH menampilkan *stack trace* atau pesan error teknis internal kepada pengguna akhir. Semua exception HARUS ditangkap dan ditampilkan sebagai pesan ramah pengguna. |

### 5.3 Persyaratan Keandalan *(Reliability Requirements)*

| ID        | Persyaratan                                                                      | Metrik Target             |
|-----------|----------------------------------------------------------------------------------|---------------------------|
| NFR-R-01  | Sistem tidak boleh *crash* saat memproses teks dengan karakter tidak biasa       | 0 *unhandled exception*   |
| NFR-R-02  | Sistem harus memberikan respons fallback jika layanan FastAPI tidak tersedia      | Pesan error ramah ≤ 5 detik|
| NFR-R-03  | Kestabilan model saat inferensi berulang (batch besar)                           | Tidak ada *memory leak* terdeteksi dalam 1 jam operasi |

### 5.4 Persyaratan Kegunaan *(Usability Requirements)*

| ID        | Persyaratan                                                                      |
|-----------|----------------------------------------------------------------------------------|
| NFR-U-01  | Antarmuka harus dapat dioperasikan oleh pengguna non-teknis tanpa panduan tambahan. |
| NFR-U-02  | Setiap fitur utama dapat dicapai dalam maksimum **3 klik** dari halaman utama.   |
| NFR-U-03  | Semua teks, label, dan pesan kesalahan dalam antarmuka menggunakan **Bahasa Indonesia**. |
| NFR-U-04  | Antarmuka harus responsif dan berfungsi pada resolusi layar minimum **1280×720**. |

### 5.5 Persyaratan Skalabilitas *(Scalability Requirements)*

Catatan: Dalam konteks penelitian ini, sistem dirancang untuk penggunaan **single-user** pada satu mesin lokal. Persyaratan skalabilitas berikut bersifat prospektif untuk pengembangan masa depan.

| ID        | Persyaratan                                                                      |
|-----------|----------------------------------------------------------------------------------|
| NFR-SC-01 | Arsitektur *microservices* memungkinkan *horizontal scaling* pada FastAPI Scraper secara independen dari Flask App. |
| NFR-SC-02 | Model inferensi dapat dimigrasikan ke GPU (CUDA) dengan perubahan minimal (hanya perlu menambahkan `.to('cuda')` pada kode PyTorch). |
| NFR-SC-03 | Layanan FastAPI dapat di-*containerize* menggunakan Docker untuk kemudahan deployment di masa depan. |

---

## 6. DATA FLOW & AI PIPELINE

### 6.1 Gambaran Umum Pipeline

Pipeline pemrosesan data dalam sistem ini terdiri dari **dua jalur utama** yang berkonvergensi pada tahap praproses dan inferensi:

```
[Jalur A: Input Langsung]      [Jalur B: Scraping]
Formulir Web / Unggah CSV  →   FastAPI → Platform X → JSON Response
         │                                    │
         └──────────────┬─────────────────────┘
                        ▼
              ┌─────────────────────┐
              │    RAW TEXT DATA    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────────────────────────┐
              │         PRAPROSES TEKS                   │
              │  1. URL & Mention Removal                │
              │  2. Karakter Khusus Removal              │
              │  3. Case Folding (lowercase)             │
              │  4. Whitespace Normalization             │
              └──────────────────┬──────────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────────┐
              │         TOKENISASI (IndoBERT)            │
              │  1. WordPiece Tokenization               │
              │  2. Penambahan Token Khusus:             │
              │     [CLS] ... [SEP]                      │
              │  3. Konversi ke input_ids                │
              │  4. Pembuatan attention_mask             │
              │  5. Padding / Truncation (max=512 token) │
              └──────────────────┬──────────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────────┐
              │      INFERENSI MODEL IndoBERT             │
              │  1. Forward Pass:                        │
              │     outputs = model(input_ids,           │
              │                     attention_mask)      │
              │  2. Ekstraksi Logits:                    │
              │     logits = outputs.logits              │
              │  3. Normalisasi Probabilitas:            │
              │     probs = softmax(logits, dim=-1)      │
              │  4. Prediksi Label:                      │
              │     label_idx = argmax(probs)            │
              └──────────────────┬──────────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────────┐
              │           OUTPUT TERSTRUKTUR             │
              │  {                                       │
              │    "label": "Positif",                   │
              │    "confidence_pos": 0.8731,             │
              │    "confidence_neg": 0.0521,             │
              │    "confidence_net": 0.0748              │
              │  }                                       │
              └──────────────────┬──────────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────────┐
              │       PRESENTASI HASIL                   │
              │  - Render Halaman Web (Single/Batch)     │
              │  - Render Dashboard (Visualisasi)        │
              │  - Generate CSV Download (Batch)         │
              └─────────────────────────────────────────┘
```

### 6.2 Detail Praproses Teks

Praproses teks diimplementasikan sebagai fungsi Python murni yang beroperasi pada string. Urutan operasi dijaga secara ketat karena urutan memengaruhi hasil akhir:

```python
# Pseudocode Alur Praproses
def preprocess_text(raw_text: str) -> str:
    text = remove_urls(raw_text)          # Step 1: Hapus URL
    text = remove_mentions(text)          # Step 2: Hapus @mention
    text = remove_hashtag_symbol(text)    # Step 3: Hapus simbol #
    text = remove_special_characters(text)# Step 4: Hapus karakter khusus
    text = to_lowercase(text)             # Step 5: Case folding
    text = normalize_whitespace(text)     # Step 6: Normalisasi spasi
    # TIDAK ada stopword removal
    return text.strip()
```

**Catatan Desain Penting**: Penghapusan *stopword* secara sengaja **dihilangkan** dari pipeline ini. Hal ini didasarkan pada pertimbangan bahwa model Transformer seperti BERT memanfaatkan konteks kalimat secara menyeluruh (*full sentence context*). Penghapusan *stopword* dapat merusak konteks gramatikal yang justru menjadi sinyal penting bagi mekanisme *self-attention* pada IndoBERT.

### 6.3 Strategi Fine-Tuning Multi-Domain (Latar Belakang Model)

Model yang digunakan adalah **IndoBERT** (`indobenchmark/indobert-base-p1`) yang telah menjalani proses *fine-tuning* dengan menggabungkan tiga dataset dari domain berbeda:

| Dataset          | Domain                     | Karakteristik Bahasa                           | Proporsi |
|------------------|-----------------------------|------------------------------------------------|----------|
| **IndoNLU SmSA** | Ulasan Produk & Berita      | Formal, terstruktur                            | ~33%     |
| **NusaX-Senti**  | Lintas domain, lintas bahasa| Formal, semi-formal, berbagai dialek           | ~33%     |
| **Kaggle Reviews**| Ulasan & Media Sosial       | Informal, slang, *code-mixing* Indonesia-Inggris| ~33%    |

Strategi ini bertujuan untuk menghasilkan model yang robust terhadap variasi linguistik yang lazim ditemukan di media sosial Indonesia, mengatasi keterbatasan model yang hanya di-*fine-tune* pada satu domain.

### 6.4 Struktur Data Antar Komponen

#### Payload Permintaan Flask → FastAPI

```json
{
  "keyword": "string — kata kunci pencarian tweet",
  "limit": "integer — jumlah tweet yang diminta (default: 100)"
}
```

#### Payload Respons FastAPI → Flask

```json
{
  "status": "success",
  "count": 98,
  "data": [
    {
      "text": "string — teks tweet mentah",
      "date": "string — ISO 8601 (contoh: 2025-06-01T10:30:00Z)"
    }
  ]
}
```

#### Struktur Output Inferensi (per-item)

```json
{
  "raw_text": "string",
  "clean_text": "string",
  "predicted_label": "Positif | Negatif | Netral",
  "confidence_positive": 0.0,
  "confidence_negative": 0.0,
  "confidence_neutral": 0.0,
  "inference_time_ms": 0.0
}
```

---

## 7. SUCCESS METRICS & ACCEPTANCE CRITERIA

### 7.1 Kriteria Kesuksesan untuk Sidang Skripsi

Sistem dinyatakan berhasil dan siap untuk didemonstrasikan dalam sidang skripsi apabila **seluruh** kriteria berikut terpenuhi:

| ID      | Kriteria                                                                                         | Cara Verifikasi                                                                    | Status Target |
|---------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|---------------|
| SM-01   | **End-to-End Fungsionalitas**: Semua 4 fitur utama (Analisis Tunggal, Batch, Scraping, Dashboard) dapat didemonstrasikan tanpa *crash* atau error kritis. | Demonstrasi langsung (*live demo*) selama sidang dengan data sampel yang disiapkan.  | WAJIB         |
| SM-02   | **Akurasi Model**: Model IndoBERT *fine-tuned* mencapai akurasi ≥ 80% pada *test set* yang ditetapkan. | Tabel evaluasi model (Accuracy, Precision, Recall, F1-Score per kelas) tercantum dalam laporan. | WAJIB         |
| SM-03   | **Analisis Teks Tunggal Responsif**: Input teks dapat diproses dan hasilnya ditampilkan dalam waktu ≤ 5 detik. | Pengujian manual dengan stopwatch selama demonstrasi.                               | WAJIB         |
| SM-04   | **Batch Processing Berfungsi**: Sistem berhasil memproses berkas CSV berisi minimal 100 baris dan menghasilkan berkas CSV unduhan yang valid. | Demonstrasi dengan berkas uji CSV yang disiapkan, diikuti pembukaan berkas hasil di Excel. | WAJIB         |
| SM-05   | **Live Scraping Berfungsi**: Sistem berhasil mengambil minimal 20 tweet untuk kata kunci yang diberikan dan menampilkan hasil analisis. | Demonstrasi *live* dengan koneksi internet aktif.                                   | WAJIB         |
| SM-06   | **Dashboard Visual Lengkap**: Keempat komponen visualisasi (Line Chart, Pie Chart, Word Cloud, Tabel) ter-render dan menampilkan data yang relevan. | Inspeksi visual langsung selama demonstrasi.                                        | WAJIB         |
| SM-07   | **Arsitektur Terpisah Terdemonstrasikan**: Kedua server (Flask port 5000 dan FastAPI port 8000) dapat ditunjukkan berjalan secara bersamaan sebagai proses terpisah. | Menampilkan dua terminal yang berjalan bersamaan, atau output `ps aux` / Task Manager. | WAJIB         |
| SM-08   | **Konsistensi Hasil Praproses**: Teks yang sama menghasilkan output praproses yang identik pada setiap pemanggilan (determinisme). | Demonstrasi dengan input yang sama dua kali berturut-turut.                         | DISARANKAN    |

### 7.2 Metrik Evaluasi Model AI *(Model Evaluation Metrics)*

Evaluasi model dilakukan menggunakan metrik standar klasifikasi multi-kelas:

| Metrik             | Formula                                                    | Target Minimum |
|--------------------|------------------------------------------------------------|----------------|
| **Accuracy**       | (TP + TN) / Total                                          | ≥ 80%          |
| **Precision (Macro)** | rata-rata Precision tiap kelas                          | ≥ 78%          |
| **Recall (Macro)** | rata-rata Recall tiap kelas                                | ≥ 78%          |
| **F1-Score (Macro)** | 2 × (Precision × Recall) / (Precision + Recall)         | ≥ 79%          |

Laporan evaluasi model HARUS menyertakan **Confusion Matrix** dan **Classification Report** per kelas (Positif, Negatif, Netral) untuk membuktikan kinerja model secara komprehensif, bukan hanya metrik agregat.

### 7.3 Definisi Selesai *(Definition of Done - DoD)*

Sebuah fitur atau *sprint* dinyatakan **Selesai** apabila:

1. ✅ Semua *User Story* dalam epik terkait telah diimplementasikan.
2. ✅ Semua *Acceptance Criteria* dari *User Story* terpenuhi.
3. ✅ Kode telah diuji secara manual dan tidak terdapat *bug* kritis yang diketahui.
4. ✅ Antarmuka pengguna konsisten dengan desain yang ditetapkan.
5. ✅ Dokumentasi teknis (komentar kode, README) telah diperbarui.
6. ✅ Sistem dapat dijalankan ulang (*restart*) tanpa kehilangan fungsionalitas.

---

## 8. GLOSSARIUM & REFERENSI

### 8.1 Glossarium Istilah

| Istilah                  | Definisi                                                                                                                             |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| **IndoBERT**             | Model *pre-trained* Transformer berbasis BERT untuk Bahasa Indonesia, dikembangkan oleh indobenchmark. Digunakan sebagai model dasar yang di-*fine-tune* dalam proyek ini. |
| **Fine-Tuning**          | Proses melatih ulang model *pre-trained* dengan dataset spesifik (*domain-specific*) untuk mengadaptasi model pada tugas tertentu.    |
| **Multi-Domain**         | Strategi pelatihan yang menggunakan data dari beragam domain (ulasan produk, berita, media sosial) untuk meningkatkan generalisasi model. |
| **Microservices**        | Paradigma arsitektur perangkat lunak di mana aplikasi dibangun sebagai kumpulan layanan kecil yang berjalan secara independen dan berkomunikasi melalui API. |
| **Sentiment Analysis**   | Tugas NLP untuk mengidentifikasi dan mengekstrak opini subjektif dari teks, biasanya diklasifikasikan menjadi Positif, Negatif, atau Netral. |
| **TLS Fingerprinting**   | Teknik identifikasi klien jaringan berdasarkan karakteristik unik dari *handshake* protokol TLS. Dalam konteks ini, digunakan untuk *menyamarkan* klien scraper agar terdeteksi sebagai browser nyata. |
| **Playwright**           | Pustaka otomasi browser *open-source* yang mendukung Chromium, Firefox, dan WebKit, digunakan untuk *headless browsing* dan scraping. |
| **Flask**                | *Micro web framework* Python yang ringan dan fleksibel, digunakan sebagai server aplikasi utama. |
| **FastAPI**              | *Web framework* Python modern berbasis Starlette yang dirancang untuk membangun API berkinerja tinggi dengan dukungan asinkronus (*asyncio*) bawaan. |
| **WordPiece**            | Algoritma tokenisasi yang digunakan oleh model BERT, memecah kata menjadi subword unit untuk menangani kosakata yang tidak dikenal (*OOV*). |
| **Softmax**              | Fungsi aktivasi yang mengubah vektor logits mentah menjadi distribusi probabilitas (semua nilai ≥ 0, total = 1). |
| **Inference / Inferensi**| Proses menggunakan model yang sudah terlatih untuk membuat prediksi pada data baru, tanpa pembaruan bobot model. |
| **Code-Mixing**          | Fenomena linguistik di mana penutur mencampurkan dua bahasa atau lebih dalam satu ujaran atau teks. Contoh: "aku lagi *overthinking* nih". |
| **Cleansing**            | Tahap praproses teks untuk membersihkan noise (URL, mention, karakter khusus) dari teks mentah. |
| **Case Folding**         | Proses normalisasi kapitalisasi teks, biasanya dengan mengubah semua karakter menjadi huruf kecil. |
| **Headless Browser**     | Browser yang beroperasi tanpa antarmuka grafis (GUI), dikendalikan sepenuhnya melalui kode program. |
| **Logits**               | Vektor skor mentah yang dihasilkan oleh lapisan terakhir model jaringan saraf sebelum diterapkan fungsi aktivasi. |
| **Agile/Scrum**          | Metodologi pengembangan perangkat lunak yang bersifat iteratif dan inkremental, mengorganisasikan pekerjaan dalam *sprint* pendek dengan ritme yang teratur. |
| **Epic**                 | Dalam konteks Agile, sebuah unit pekerjaan besar yang dapat dipecah menjadi beberapa *User Story* yang lebih kecil. |
| **User Story**           | Deskripsi singkat fitur perangkat lunak dari perspektif pengguna akhir, biasanya dalam format: "Sebagai [peran], saya ingin [tindakan] agar [manfaat]". |

### 8.2 Referensi Teknologi Kunci

| Teknologi / Pustaka           | Versi Minimum | Fungsi dalam Sistem                                     |
|-------------------------------|---------------|---------------------------------------------------------|
| Python                        | 3.10+         | Bahasa pemrograman utama untuk Flask dan FastAPI        |
| Flask                         | 3.0+          | Framework server aplikasi web utama                    |
| FastAPI                       | 0.111+        | Framework microservice scraper asinkronus               |
| Uvicorn                       | 0.29+         | ASGI server untuk menjalankan FastAPI                   |
| PyTorch                       | 2.0+          | Framework inferensi model deep learning                 |
| Transformers (Hugging Face)   | 4.40+         | Memuat model IndoBERT dan tokenizer                     |
| Playwright (Python)           | 1.44+         | Engine otomasi browser untuk scraping                   |
| pandas                        | 2.0+          | Pemrosesan dan manipulasi data CSV                      |
| Bootstrap                     | 5.3+          | Framework CSS untuk antarmuka pengguna responsif        |
| Chart.js                      | 4.0+          | Pustaka JavaScript untuk line chart dan pie chart       |
| WordCloud2.js                 | 1.2+          | Pustaka JavaScript untuk rendering word cloud           |

### 8.3 Dataset Referensi

| Nama Dataset          | Sumber                                  | Lisensi       |
|-----------------------|-----------------------------------------|---------------|
| IndoNLU SmSA          | IndoNLU Benchmark (GitHub/HuggingFace)  | MIT           |
| NusaX-Senti           | NusaX Project (GitHub/HuggingFace)      | Apache 2.0    |
| Kaggle Indonesian Sentiment | Kaggle Datasets (publik)          | CC BY 4.0     |

---

*Dokumen ini merupakan produk hidup (living document) yang akan diperbarui seiring perkembangan implementasi. Versi ini adalah versi final yang ditujukan untuk sidang skripsi.*

---

**© 2025 — Dokumen PRD Sistem Klasifikasi Sentimen Teks Media Sosial Menggunakan IndoBERT**
*Disiapkan oleh: Mahasiswa Peneliti | Dibimbing oleh: Dosen Pembimbing | Ditujukan untuk: Majelis Penguji Sidang Skripsi*
