---
name: clean-code-indonesia
description: Standar wajib penulisan Clean Code berbahasa Indonesia untuk proyek Django (Respondent Exchanger) yang mudah dibaca dan dipahami seluruh anggota kelompok.
trigger: always_on
---

# 🇮🇩 Aturan Wajib: Clean Code Ramah Tim (Standar Django — Respondent Exchanger)

Seluruh kode baru yang ditulis di repositori ini **WAJIB** mengutamakan **keterbacaan (*readability*)** dengan penamaan serta komentar berbahasa Indonesia yang jelas, agar seluruh anggota kelompok dapat memahami, memodifikasi, dan menjelaskan alur kode dengan lancar saat presentasi/sidang.

---

## 1. Standar Penamaan (`Naming Convention`)

### A. Nama Variabel & Fungsi Python / Django (`snake_case` Bahasa Indonesia)
Ikuti PEP 8 (`snake_case` untuk variabel & fungsi, `PascalCase` untuk `class`). Gunakan nama deskriptif dalam Bahasa Indonesia untuk variabel lokal, fungsi pembantu, dan context view — **bukan** singkatan tidak jelas:
- ❌ **SALAH (Singkatan / Tidak Jelas):**
  `q_list`, `usr`, `res`, `cnt`, `get_q()`, `calc_pts()`
- ✅ **BENAR (Bahasa Indonesia Jelas):**
  `daftar_kuesioner`, `data_pengguna`, `hasil_pencarian`, `jumlah_responden`, `ambil_kuesioner_aktif()`, `hitung_total_poin()`

*(Catatan: Nama model, field database, dan method bawaan Django/SRS yang sudah ada — seperti `Questionnaire`, `owner`, `status`, `objects.filter()`, `get_object_or_404()`, `render()`, `redirect()`, `clean()`, `save()`, `__str__()` — tetap menggunakan nama aslinya agar selaras dengan migrasi dan framework Django).*

### B. Nama Key Context Template & Variabel JavaScript
- **Context dictionary pada Django View (`snake_case` Bahasa Indonesia):**
  Gunakan key yang mudah dipahami di template HTML, misalnya:
  `context = {'daftar_kuesioner': daftar_kuesioner, 'total_responden': total_responden, 'pesan_error': pesan_error}`
- **Variabel & fungsi JavaScript (`camelCase` Bahasa Indonesia):**
  Jika menulis script di template/static, gunakan `camelCase` yang jelas (misal: `daftarPertanyaan`, `waktuTersisa`, `validasiJawaban()`).

---

## 2. Prinsip Clean Code Ramah Mahasiswa (Bukan Kode "Pintar" yang Membingungkan)

1. **Keterbacaan Lebih Penting daripada Baris Pendek (*Readability over Brevity*):**
   - **DILARANG** memadatkan logika kompleks ke dalam 1 baris panjang (*nested ternary* `a if b else c if d else e` atau *list comprehension* berlapis).
   - Pecah proses menjadi langkah-langkah berurutan dengan variabel penjelas yang mudah diikuti mata.
   - **Contoh Buruk (Susah Dibaca):**
     ```python
     label = f"{k.reward} Poin" if k.reward > 0 else ("Selesai" if k.status == 'published' else "Draf")
     ```
   - **Contoh Baik (Clean Code):**
     ```python
     # Tentukan label status kuesioner agar mudah dibaca di template
     if kuesioner.status == Questionnaire.Status.PUBLISHED:
         label_status = 'Terbit'
     elif kuesioner.status == Questionnaire.Status.HIDDEN:
         label_status = 'Disembunyikan'
     else:
         label_status = 'Draf'
     ```

2. **Komentar Penjelas Berbahasa Indonesia:**
   - Berikan komentar singkat 1 baris (`# ...` di Python atau `// ...` di JavaScript) dalam Bahasa Indonesia di atas blok logika penting, seperti validasi form, perhitungan poin/kuota responden, filter query Django ORM, atau pengecekan hak akses.
   - Tujuannya agar setiap anggota kelompok langsung mengerti fungsi blok kode tersebut dalam sekali baca.

3. **Anti Over-Engineering (Tetap Sederhana & Lurus):**
   - Gunakan arsitektur standar MVT Django (`Models` → `Views` → `Templates`, beserta `Forms` dan `URLs`).
   - Jangan membuat *Design Pattern* berlapis-lapis (seperti *Repository*, *DTO*, *Service Factory*, *Mixin* abstrak berlapis) atau meng-install library tambahan yang tidak diminta.
   - Satu fungsi/view hanya mengerjakan satu tugas yang jelas (*Single Responsibility*).
