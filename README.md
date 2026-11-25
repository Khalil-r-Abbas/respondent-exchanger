# Respondent Exchanger

Platform pertukaran kuesioner berbasis **Django** yang membantu mahasiswa dan peneliti mengumpulkan responden secara adil melalui sistem poin berbasis buku besar (*point ledger*), validasi waktu pengisian di sisi server, serta verifikasi akun.

---

## Fitur yang Tersedia Saat Ini

1. **Autentikasi & Manajemen Akun (`accounts`, `/akun/...`)**
   - Pendaftaran akun (`/akun/daftar/`) dengan validasi username (`3–20` karakter alfanumerik/garis bawah), email unik, pemblokiran domain *disposable email*, pencatatan IP pendaftaran/terakhir, dan pengiriman tautan verifikasi email (berlaku 24 jam).
   - Login (`/akun/login/`) menggunakan username atau email, pembatasan percobaan gagal (terkunci 15 menit setelah 5 kali gagal), dan penolakan akun terblokir (`is_blocked=True`).
   - Dasbor akun (`/akun/dasbor/`), kirim ulang verifikasi email (jeda 60 detik), lupa & reset kata sandi (`/akun/lupa-sandi/`), panel ringkasan admin (`/akun/panel-admin/`), dan tabel matriks hak akses 3 peran (`/akun/hak-akses/`).

2. **Pembuat & Pengelola Kuesioner (`forms_app`, `/kuesioner/...`)**
   - Daftar kuesioner milik pengguna (`/kuesioner/`) yang dipisahkan menjadi *Draf*, *Sedang terbit*, dan *Berakhir atau ditutup*.
   - Pembuat kuesioner (`/kuesioner/baru/`, `/kuesioner/<id>/edit/`) dengan batas maksimal 6 draf per pengguna dan 20 pertanyaan per kuesioner (mendukung tipe `short_text`, `long_text`, `single_choice`, `multiple_choice`, `dropdown`, dan `rating`).
   - Pratinjau & berbagi kode/tautan (`/kuesioner/<id>/preview/`), penerbitan (`/kuesioner/<id>/publish/`, masa berlaku 1–7 hari, maksimal 3 kuesioner aktif, wajib `email_verified=True`), duplikasi draf, penghapusan kuesioner, serta halaman pratinjau publik read-only (`/f/<link_code>/`).

3. **Pengisian Kuesioner & Sistem Poin (`forms_app` & `core/points.py`, `/q/<link_code>/`)**
   - Pengisian kuesioner publik (`/q/<link_code>/`) dan halaman ringkasan selesai (`/q/<link_code>/selesai/`).
   - Penegakan waktu minimum pengisian berbasis jam server (`SubmissionSession`, `10–20` detik per pertanyaan). Pengisian yang terlalu cepat tetap tersimpan (`is_too_fast=True`) tanpa memperoleh poin.
   - Pencatatan poin (`1–20` poin sesuai jumlah pertanyaan) secara *append-only* ke `PointLedger` untuk responden login yang emailnya terverifikasi, tidak diblokir, bukan pemilik kuesioner, dan memenuhi waktu minimum.
   - Pencegahan pengisian ganda per akun (`respondent`) maupun per sesi anonim (`anonymous_key`).

4. **Database & Data Demo (`core`)**
   - 9 model relasional sesuai spesifikasi SRS (`User`, `Questionnaire`, `Question`, `SubmissionSession`, `Response`, `Answer`, `Report`, `PointLedger`, `AdminAuditLog`) dan Django Admin (`/admin/`).
   - Perintah `python manage.py seed_demo` untuk mengisi data contoh (5 pengguna, 8 kuesioner, contoh respons, dan entri poin).

> **Catatan Status Pengembangan:** Halaman beranda utama (`/`) saat ini belum tersedia (mengakses `/` akan mengembalikan `404`). Fitur daftar kuesioner publik untuk dicari responden, formulir pelaporan (`Report`) di UI publik, serta analitik/ekspor hasil jawaban pembuat kuesioner masih dalam tahap pengembangan berikutnya.

---

## Prasyarat

Sebelum memulai, pastikan komputer Anda sudah terpasang:
- **Python** (disarankan versi 3.10 ke atas; proyek dikembangkan dengan Django 6.1.3)
- **Git**
- **PostgreSQL** (opsional jika memilih mode SQLite untuk pengembangan lokal)

---

## Cara Menjalankan Project di Lokal

### 1. Clone Repository
```bash
git clone https://github.com/Khalil-r-Abbas/respondent-exchanger.git
cd respondent-exchanger
```

### 2. Buat & Aktifkan Virtual Environment
```bash
python -m venv venv
```

Aktifkan virtual environment sesuai sistem operasi:
* **Windows (PowerShell/CMD):**
  ```bash
  venv\Scripts\activate
  ```
* **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment (`.env`)
Salin file `.env.example` menjadi `.env`, lalu sesuaikan nilainya:
```bash
# Windows (CMD) / macOS / Linux
copy .env.example .env   # atau: cp .env.example .env
```

Atur isi `.env`:
- Pastikan `DEBUG=True` saat menjalankan di lokal (di `.env.example` nilai `DEBUG=` masih kosong, yang jika dibiarkan kosong akan terbaca sebagai `False`).
- **Opsi A — Menggunakan PostgreSQL (bawaan):**
  Buat database bernama `respondent_exchange` di PostgreSQL lokal, lalu isi kredensial di `.env`:
  ```env
  SECRET_KEY=ganti-dengan-secret-key-lokal
  DEBUG=True
  DEV_AUTO_LOGIN=False
  ALLOWED_HOSTS=localhost,127.0.0.1

  DB_ENGINE=django.db.backends.postgresql
  DB_NAME=respondent_exchange
  DB_USER=postgres
  DB_PASSWORD=password_postgres_anda
  DB_HOST=localhost
  DB_PORT=5432
  ```
- **Opsi B — Menggunakan SQLite (tanpa install PostgreSQL):**
  Ubah `DB_ENGINE` dan `DB_NAME` di `.env`:
  ```env
  DB_ENGINE=django.db.backends.sqlite3
  DB_NAME=db.sqlite3
  ```

*(Opsional)* Jika ingin menguji halaman pembuat kuesioner (`/kuesioner/...`) tanpa login manual saat pengembangan lokal, set `DEV_AUTO_LOGIN=True` (hanya aktif ketika `DEBUG=True`, otomatis masuk sebagai akun `demo_builder`).

### 5. Migrasi Database & Data Demo
Jalankan migrasi untuk membentuk seluruh tabel database:
```bash
python manage.py migrate
```

*(Disarankan)* Isi data contoh untuk keperluan uji coba lokal:
```bash
python manage.py seed_demo
```
Akun demo yang dibuat oleh `seed_demo` (`andi_sutanto`, `budi_pratama`, `citra_lestari`, `dewi_anggraini`, `eko_wijaya`) seluruhnya menggunakan kata sandi **`DemoPass123!`**.

*(Opsional)* Buat akun admin/superuser untuk mengakses `/admin/` dan `/akun/panel-admin/`:
```bash
python manage.py createsuperuser
```

### 6. Jalankan Server Lokal
```bash
python manage.py runserver
```

Email verifikasi dan reset kata sandi pada mode default dicetak langsung ke terminal server (`console.EmailBackend`).

---

## Rute URL Utama

| Path | Keterangan |
| :--- | :--- |
| `/akun/login/` | Halaman masuk (username atau email) |
| `/akun/daftar/` | Halaman pendaftaran akun baru |
| `/akun/dasbor/` | Dasbor akun, status verifikasi email, dan total poin |
| `/akun/hak-akses/` | Tabel pembagian hak akses (Pengunjung, Pengguna, Admin) |
| `/akun/panel-admin/` | Ringkasan moderasi akun khusus Admin |
| `/kuesioner/` | Daftar kuesioner milik pengguna |
| `/kuesioner/baru/` | Pembuat kuesioner baru |
| `/f/<link_code>/` | Pratinjau publik kuesioner (read-only) |
| `/q/<link_code>/` | Halaman pengisian kuesioner untuk responden |
| `/q/<link_code>/selesai/` | Ringkasan hasil pengisian dan perolehan poin |
| `/admin/` | Panel admin bawaan Django |

---

## Menjalankan Pengujian

Untuk menjalankan unit test & integration test:
```bash
python manage.py test
```
*(Pastikan database yang terkonfigurasi di `.env` aktif, atau gunakan `DB_ENGINE=django.db.backends.sqlite3` saat menjalankan tes).*

---

## Struktur Direktori & Dokumentasi

```text
respondent_exchanger/
├── accounts/        # Autentikasi, verifikasi email, reset sandi, dan hak akses 3 peran
├── core/            # Pengaturan Django, ledger poin, log audit admin, & command seed_demo
├── forms_app/       # Model kuesioner, builder, validasi pengisian, dan timer server
├── docs/            # Dokumentasi teknis proyek
│   ├── perbandingan_erd_srs.md
│   ├── skema_database.md
│   └── tabel_hak_akses.md
├── manage.py
└── requirements.txt
```

---

## Catatan Penting untuk Pengembangan
- Setiap kali membuka terminal baru untuk mengerjakan project, **selalu aktifkan `venv` terlebih dahulu**.
- Jangan pernah melakukan *commit* file `.env` atau `db.sqlite3` ke repository.
- Jika menginstall library baru menggunakan `pip install <nama-library>`, perbarui `requirements.txt` sebelum *commit* dan *push*:
  ```bash
  pip freeze > requirements.txt
  ```
