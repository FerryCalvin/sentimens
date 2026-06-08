# BAB 1: PENDAHULUAN

## 1.1 Latar Belakang
Di era digital saat ini, media sosial dan portal berita online telah menjadi wadah utama bagi masyarakat untuk menyampaikan opini, keluhan, maupun apresiasi terhadap berbagai entitas, baik itu produk komersial, layanan publik, hingga tokoh politik. Jumlah data teks yang diproduksi setiap hari mencapai jutaan, sehingga menjadikannya tambang informasi yang sangat berharga (big data). Namun, volume data yang begitu besar ini membuat analisis manual oleh manusia menjadi tidak efisien, memakan waktu, dan sangat rentan terhadap bias subjektif. Oleh karena itu, diperlukan suatu sistem otomatis yang mampu mengekstraksi sentimen dari teks secara cepat, terukur, dan objektif.

Pendekatan *Sentiment Analysis* (Analisis Sentimen) telah terbukti efektif dalam memetakan opini publik menjadi polaritas yang jelas, seperti positif, negatif, atau netral. Seiring dengan perkembangan *Natural Language Processing* (NLP), pemodelan berbasis *Transformer*, khususnya *Bidirectional Encoder Representations from Transformers* (BERT), telah menjadi standar baru (state-of-the-art) dalam memahami konteks bahasa manusia yang kompleks. Dalam konteks Bahasa Indonesia, model **IndoBERT** yang dikembangkan khusus untuk menangkap nuansa lokal, struktur tata bahasa, dan gaya bahasa percakapan (slang) menawarkan tingkat akurasi yang jauh lebih tinggi dibandingkan algoritma machine learning tradisional (seperti Naive Bayes atau SVM).

Penelitian ini mengusulkan pengembangan platform **"Sentiments"**, yaitu sebuah sistem cerdas ujung-ke-ujung (end-to-end) untuk analisis sentimen lintas domain (multi-domain). Sistem ini tidak hanya berfokus pada pelatihan model NLP saja, melainkan menggabungkannya dengan *web scraping* asinkron untuk pengambilan data opini masyarakat secara *real-time*, arsitektur pemrosesan latar belakang (*background processing*) yang terisolasi untuk menghindari *bottleneck* performa, serta disajikan dalam antarmuka *dashboard* web interaktif yang memudahkan pemangku kepentingan (stakeholder) mengambil keputusan berdasarkan data (*data-driven decision making*).

## 1.2 Rumusan Masalah
Berdasarkan latar belakang yang telah diuraikan, rumusan masalah dalam penelitian ini adalah sebagai berikut:
1. Bagaimana cara merancang bangun arsitektur sistem berbasis *microservices* (memisahkan *web scraping* dan inferensi model) untuk analisis sentimen agar memiliki skalabilitas dan kecepatan pemrosesan yang optimal?
2. Sejauh mana efektivitas model IndoBERT *fine-tuned* dalam mengklasifikasikan polaritas sentimen (Positif, Negatif, Netral) pada teks berbahasa Indonesia lintas domain?
3. Bagaimana cara memvisualisasikan insight dan metrik analisis sentimen secara informatif dan interaktif agar mudah dipahami oleh pengguna akhir tanpa latar belakang teknis?

## 1.3 Batasan Masalah
Untuk menjaga fokus penelitian, batasan masalah ditetapkan sebagai berikut:
1. **Bahasa:** Analisis sentimen hanya dibatasi pada korpus teks yang menggunakan Bahasa Indonesia (termasuk bahasa percakapan dan slang yang umum digunakan di media sosial).
2. **Kategori Sentimen:** Output klasifikasi hanya terbagi ke dalam tiga kelas polaritas: Positif, Negatif, dan Netral. Tidak mencakup analisis emosi secara spesifik (seperti marah, sedih, atau takut).
3. **Sumber Data:** Fitur *live scraping* dibatasi pada platform berita daring dan Twitter/X (melalui emulasi *browser headless*), serta didukung fitur pengunggahan dataset kustom berbasis CSV.
4. **Metode *Scraping*:** Menggunakan pustaka *Playwright* tanpa kebutuhan autentikasi API *official* secara langsung, dikelola via layanan API FastAPI yang terpisah.
5. **Infrastruktur Model:** Inferensi model IndoBERT dijalankan secara lokal (menggunakan PyTorch pada komputasi CPU/GPU standar) tanpa dideploy pada ekosistem komputasi awan skala besar (*high-end cloud cluster*).

## 1.4 Tujuan Penelitian
Adapun tujuan yang ingin dicapai melalui pelaksanaan penelitian ini adalah:
1. Mengimplementasikan model IndoBERT yang telah di-*fine-tune* pada arsitektur web aplikasi komprehensif, sehingga dapat memproses kalimat opini lintas domain dengan tingkat akurasi di atas 80%.
2. Mengembangkan arsitektur *Decoupled System* yang mengintegrasikan Flask (untuk antarmuka web dan orkestrasi) dan FastAPI (khusus untuk operasi web scraping I/O bound yang berat).
3. Membangun *Dashboard Sentiments*, antarmuka pengguna berbasis *Single Page Application* (SPA) dengan fitur visualisasi interaktif dan sistem manajemen pemrosesan asinkron untuk menangani beban data berskala menengah hingga besar.

## 1.5 Manfaat Penelitian
Manfaat yang diharapkan dari hasil penelitian ini meliputi:
1. **Manfaat Teoritis:** Memberikan rujukan keilmuan dan kontribusi praktis tentang integrasi model pra-latih (Pre-Trained Language Models) seperti IndoBERT ke dalam sebuah produk perangkat lunak ujung-ke-ujung (E2E), bukan sebatas eksperimen *Jupyter Notebook*.
2. **Manfaat Praktis:** Menyediakan *tool* atau alat bantu yang langsung dapat digunakan oleh praktisi, humas (Public Relations), maupun analis pasar untuk memahami persepsi dan sentimen publik dalam waktu singkat, sehingga dapat mempercepat siklus pengambilan keputusan.
3. **Manfaat Ekademis:** Menjadi fondasi dasar (*baseline*) untuk pengembangan sistem monitoring analitik sosial di masa depan yang berfokus pada linguistik Bahasa Indonesia.
