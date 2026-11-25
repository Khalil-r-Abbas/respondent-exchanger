# Tabel Hak Akses per Peran — Respondent Exchanger

Dokumen ini merupakan acuan resmi pembagian peran dan pembatasan akses halaman pada modul `accounts` (`accounts/permissions.py`).

## 1. Definisi Tiga Peran

1. **Pengunjung (`pengunjung`)**
   - Pengguna yang belum masuk (`request.user.is_authenticated == False`).
2. **Pengguna (`pengguna`)**
   - Pengguna yang sudah masuk dan tidak memiliki flag admin (`is_staff=False`, `is_superuser=False`).
   - Memiliki dua status turunan:
     - **Belum Verifikasi Email** (`email_verified=False`)
     - **Terverifikasi Email** (`email_verified=True`)
   - Jika `is_blocked=True`, pengguna tidak diizinkan masuk dan sesi aktifnya akan dikeluarkan secara paksa (`403 Forbidden`).
3. **Admin (`admin`)**
   - Pengguna dengan `is_staff=True` atau `is_superuser=True` (dan `is_blocked=False`).

---

## 2. Matriks Hak Akses

| Fitur / Halaman | Pengunjung | Pengguna (Belum Verifikasi) | Pengguna (Terverifikasi) | Admin |
| :--- | :--- | :--- | :--- | :--- |
| Halaman Daftar (`/akun/daftar/`) | Boleh | Dialihkan ke Dasbor | Dialihkan ke Dasbor | Dialihkan ke Dasbor |
| Halaman Login (`/akun/login/`) | Boleh | Dialihkan ke Dasbor | Dialihkan ke Dasbor | Dialihkan ke Dasbor |
| Lupa & Reset Kata Sandi (`/akun/lupa-sandi/`) | Boleh | Boleh | Boleh | Boleh |
| Verifikasi Email (`/akun/verifikasi-email/<token>/`) | Boleh | Boleh | Boleh | Boleh |
| Tabel Hak Akses (`/akun/hak-akses/`) | Boleh | Boleh | Boleh | Boleh |
| Mengisi Kuesioner Publik (`allow_anonymous=True`) | Boleh (tanpa poin) | Boleh (tanpa poin) | Boleh (dapat poin) | Boleh (dapat poin) |
| Mengisi Kuesioner Khusus Akun (`allow_anonymous=False`) | Ditolak (wajib login) | Boleh (tanpa poin) | Boleh (dapat poin) | Boleh (dapat poin) |
| Dasbor Akun (`/akun/dasbor/`) & Kirim Ulang Verifikasi | Ditolak (ke Login) | Boleh | Boleh | Boleh |
| Membuat & Menerbitkan Kuesioner | Ditolak (ke Login) | Ditolak (wajib verifikasi) | Boleh | Boleh |
| Melaporkan Kuesioner Bermasalah | Ditolak (ke Login) | Ditolak (wajib verifikasi) | Boleh | Boleh |
| Panel Admin (`/akun/panel-admin/` & `/admin/`) | Ditolak (ke Login) | Ditolak (`403 Forbidden`) | Ditolak (`403 Forbidden`) | Boleh |

---

## 3. Dekorator Pembatasan Akses untuk Tim (`accounts/permissions.py`)

Anggota tim lain (fitur kuesioner, laporan, dan admin) dapat langsung menggunakan dekorator berikut di `views.py`:

* `@wajib_pengunjung` — hanya untuk pengunjung belum login.
* `@wajib_pengguna()` — wajib login dan tidak diblokir.
* `@wajib_pengguna(perlu_verifikasi_email=True)` — wajib login, tidak diblokir, dan sudah verifikasi email (cocok untuk fitur terbit kuesioner & pelaporan).
* `@wajib_admin` — khusus admin (`is_staff` / `is_superuser`).
