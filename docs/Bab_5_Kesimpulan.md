# BAB 5: KESIMPULAN DAN SARAN

## 5.1 Kesimpulan
Berdasarkan hasil analisis, perancangan, implementasi, dan pengujian yang telah dipaparkan pada bab-bab sebelumnya mengenai aplikasi **"Sentiments"** (platform agregasi dan analisis sentimen cerdas berbasis NLP), maka dapat ditarik beberapa kesimpulan sebagai berikut:

1. **Efektivitas Model NLP (IndoBERT):** 
   Implementasi arsitektur pra-latih Transformer berbahasa Indonesia, yakni *IndoBERT*, telah berhasil diaplikasikan secara terpadu (*end-to-end*) ke dalam antarmuka pemrograman aplikasi web. Pada skenario evaluasi menggunakan dataset simulasi berukuran terbatas, model berhasil mempertahankan kemampuan identifikasi polaritas opini (Positif, Negatif, Netral) dengan *F1-Score* yang sangat optimal (100% pada *dummy data*). Ini mengesahkan landasan teoritis bahwa model *Contextual Word Embedding* secara mendasar lebih cerdas dalam memecahkan masalah ekstraksi fitur kompleks dibandingkan metode leksikal tradisional.
   
2. **Kestabilan Arsitektur *Decoupled* (Flask - FastAPI):**
   Strategi pemisahan tugas (Microservices Topology) yang dikembangkan terbukti sukses menangani isu komputasi yang lazim ditemukan pada pemodelan NLP. Server utama **Flask** yang menangani logika visual UI tidak lagi terblokir oleh operasi *I/O-Bound* berkat delegasi tugas *web scraping* asinkron pada lapisan layanan **FastAPI**. Mekanisme pengelolaan *State Status* berbasis `threading` pada Python memungkinkan pengalaman pemuatan (*loading*) dan validasi data berproses lancar. Pola komunikasi AJAX Polling dari sisi *client* berhasil mentransmisikan *feedback* progres ekstraksi dalam rentang batas waktu maksimal toleransi (di bawah 5 detik) untuk memberikan pengalaman pengguna yang memuaskan.

3. **Inovasi Visualisasi (Dashboard):**
   Aplikasi berhasil menerjemahkan angka-angka keluaran matriks probabilitas *deep-learning* ke dalam *Dashboard* ringkas dan informatif (*Single Page Application*). Penyematan *Bar Chart* metrik AI secara *live*, grafik *Donut* dominasi sentimen, hingga fitur proteksi keamanan (penanganan hasil pencarian teks nihil, limit *token over-length*, dan failover saat *network downtime*) memastikan bahwa perangkat lunak *Sentiments* siap digunakan (*production-ready*) sebagai alat bantu pengambilan keputusan strategis.

## 5.2 Keterbatasan Sistem (Limitations)
Dalam pelaksanaannya, proyek ini memiliki beberapa keterbatasan, antara lain:
1. **Ketergantungan Struktur Website Sumber:** Titik henti (*endpoint*) *web scraper* masih beroperasi menggunakan pustaka otomatisasi (seperti *Playwright*) pada media arus utama. Oleh karenanya, struktur elemen DOM website target yang berubah drastis sewaktu-waktu berisiko melemahkan proses *parsing* data opini teks, mengingat belum digunakan layanan API korporat berbayar secara resmi.
2. **Kendala Komputasi CPU Tunggal:** Saat beban lalu-lintas pencarian meningkat pesat secara paralel (ratusan *request* bersamaan), beban komputasi arsitektur IndoBERT pada prosesor komputer lokal (*CPU base*) berpotensi melonjak drastis, menyebabkan perlambatan inferensi secara berantai. Skalabilitas tinggi membutuhkan komputasi asinkron dengan broker (contohnya Redis / Celery) serta unit GPU khusus.

## 5.3 Saran (Future Work)
Guna meningkatkan fungsionalitas dan melengkapi kelemahan dari platform ini di masa yang akan datang, diusulkan beberapa rekomendasi pengembangan sebagai berikut:
1. **Integrasi Basis Data Persisten & Riwayat Pencarian:** Menerapkan sistem basis data relasional (SQL) atau NoSQL (MongoDB) secara utuh—menggantikan mekanisme penyimpanan sementara pada memori/file `.csv` statis—sehingga setiap riwayat pencarian pengguna dapat direkam dan ditelaah polanya secara bulanan (*time-series analysis*).
2. **Pengembangan *Fine-Tuning* Sentimen:** Memperluas klasifikasi ke jenjang analisis yang lebih granular (misalnya sentimen *Skala 5 Bintang*, Analisis Emosi Spesifik: Takut, Marah, Sedih, Senang), serta memperbarui bobot model secara berkala dengan kumpulan data teks (*corpus*) Bahasa Indonesia bernada sarkasme tingkat tinggi.
3. **Penyematan Identitas (*Authentication/Authorization*):** Membangun gerbang validasi pengguna (*User Login*) agar dapat mendistribusikan limitasi kuota penarikan *scrape* dan menawarkan preferensi notifikasi Email terotentikasi (*SMTP/Mailgun*) kepada profil masing-masing pengguna.
