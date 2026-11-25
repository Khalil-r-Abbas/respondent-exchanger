# Perbandingan ERD Minggu ke-2 vs Data Model SRS

Dokumen ini mencatat selisih antara rancangan awal (`PROYEK/UML/ERD.png`) dengan spesifikasi pada `PROYEK/Dokumen/SRS.pdf` (Bagian 7: Kebutuhan Data), yang menjadi acuan implementasi model Django di branch `fitur/database`.

## Ringkasan Selisih Utama

| Aspek | ERD Minggu ke-2 | Data Model SRS (Acuan Implementasi) |
| :--- | :--- | :--- |
| **Jumlah Entitas** | 4 tabel (`USERS`, `SURVEYS`, `SURVEY_SUBMISSIONS`, `SURVEY_REPORTS`) | 9 entitas (`Pengguna`, `Kuesioner`, `Pertanyaan`, `Sesi pengisian`, `Respons`, `Jawaban`, `Buku besar poin`, `Laporan`, `Log audit admin`) |
| **Soal & Jawaban** | Disimpan sebagai berkas eksternal (`file_location`, `answer_file_location`) | Disimpan langsung di database relasional melalui tabel `Pertanyaan` dan `Jawaban` (`jsonb`) |
| **Mekanisme Poin** | Kolom saldo tunggal `USERS.point_balance` dan `SURVEYS.reward_points` | Buku besar *append-only* (`core_point_ledger`) dengan `SET_NULL` saat kuesioner dihapus dan flag `is_revoked` |
| **Timer & Sesi Pengisian** | Hanya mencatat `started_at` dan `submitted_at` di `SURVEY_SUBMISSIONS` | Dipisah ke `Sesi pengisian` (`forms_submission_session`) untuk menegakkan batas 1 sesi aktif, timeout, dan status `is_too_fast` di `Respons` |
| **Status Kedaluwarsa** | Disimpan di enum `status` (`closed`, `suspended`) | Status hanya `draft`, `published`, `hidden`, `removed`; kedaluwarsa dihitung secara dinamis dari `expires_at` |
| **Identitas Pengguna** | `name`, `role`, `point_balance`, `is_active` | `username` (3–20 karakter alfanumerik/underscore), `email` (unik), `email_verified`, `is_blocked`, `registration_ip`, `last_ip` |
| **Batas Unik & Relasi** | Belum ada constraint unik eksplisit di ERD | Unik 1 laporan per `(questionnaire, reporter)`; unik 1 respons per `(questionnaire, respondent)` untuk akun terdaftar dan per `(questionnaire, anonymous_key)` untuk anonim |
| **Moderasi & Audit** | Kolom review admin diletakkan di `SURVEY_REPORTS` (`admin_id`, `status`, `admin_action_note`, `resolved_at`) | Pelaporan fokus ke `Laporan` (`forms_report`), sementara semua tindakan moderasi dicatat di `Log audit admin` (`core_admin_audit_log`) |

## Keputusan Penyelarasan ke Kode

1. **Mengikuti SRS secara penuh** pada implementasi model Django agar seluruh kebutuhan fungsional (`FR-01` s.d. `FR-74`) dapat berjalan tanpa migrasi ulang di minggu berikutnya.
2. **Aturan penghapusan (`on_delete`)**:
   - Menghapus **Kuesioner** menghapus `Pertanyaan`, `Sesi pengisian`, `Respons`, `Jawaban`, dan `Laporan` terkait (`CASCADE`), tetapi menjaga `Buku besar poin` tetap ada (`SET_NULL`).
   - Menghapus **Pengguna** menghapus `Kuesioner` miliknya dan `Buku besar poin` miliknya (`CASCADE`), serta menjadikan `Respons` yang pernah dikirimnya anonim (`respondent = NULL` via `SET_NULL`).
3. **Indeks Kinerja**:
   - Menambahkan indeks pada `forms_questionnaire.link_code` dan `forms_questionnaire.expires_at` (serta indeks gabungan `status, expires_at`) untuk daftar beranda dan validasi tautan publik.
