# Respondent Excnager


## Prasyarat

Sebelum memulai, pastikan komputer Anda sudah terinstall:
- **Python** (disarankan versi 3.10 ke atas)
- **Git**

## Cara Menjalankan Project di Lokal

Ikuti langkah-langkah berikut untuk menyetup dan menjalankan project ini di komputer Anda:

### 1. Clone Repository
Buka terminal (Command Prompt, PowerShell, atau Terminal di VS Code), lalu unduh source code project ini:

```bash
git clone https://github.com/Khalil-r-Abbas/respondent-exchanger.git
cd respondent_exchanger
```

### 2. Buat & Aktifkan Virtual Environment
Buat lingkungan kerja Python yang terisolasi agar library tidak tercampur dengan sistem global:

```bash
# Membuat virtual environment
python -m venv venv
```

Aktifkan virtual environment sesuai sistem operasi yang digunakan:
* **Windows:**
  ```bash
  venv\Scripts\activate
  ```
* **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```
*(Pastikan muncul tanda `(venv)` di sebelah kiri baris terminal Anda sebelum melanjutkan).*

### 3. Install Dependencies
Install seluruh paket dan library yang dibutuhkan project melalui file `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Database & Migrasi
Jalankan migrasi untuk membuat struktur tabel database lokal (`db.sqlite3`):

```bash
python manage.py migrate
```

*(Opsional)* Jika perlu mengakses halaman admin Django (`/admin`), buat akun superuser terlebih dahulu:
```bash
python manage.py createsuperuser
```

### 5. Jalankan Server Lokal
Nyalakan server development Django:

```bash
python manage.py runserver
```

Buka browser dan akses alamat **`http://127.0.0.1:8000/`**.

---

## Catatan Penting untuk Pengembangan
- Setiap kali membuka terminal baru untuk mengerjakan project, **selalu aktifkan `venv` terlebih dahulu**.
- Jika menginstall library baru menggunakan `pip install <nama-library>`, perbarui daftar paket sebelum melakukan *commit* dan *push*:
  ```bash
  pip freeze > requirements.txt
  ```