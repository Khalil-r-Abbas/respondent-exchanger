import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.permissions import tentukan_peran_pengguna
from accounts.utils import apakah_email_sekali_pakai, buat_token_verifikasi_email

User = get_user_model()


class UjiAutentikasiDanHakAkses(TestCase):
    """Pengujian lengkap modul autentikasi, pembatasan login, blokir email, dan 3 peran."""

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

        self.pengguna_biasa = User.objects.create_user(
            username='andi_user',
            email='andi@kampus.ac.id',
            password='SandiKuat123!',
            email_verified=True,
        )
        self.pengguna_belum_verifikasi = User.objects.create_user(
            username='budi_baru',
            email='budi@kampus.ac.id',
            password='SandiKuat123!',
            email_verified=False,
        )
        self.pengguna_diblokir = User.objects.create_user(
            username='citra_blokir',
            email='citra@kampus.ac.id',
            password='SandiKuat123!',
            email_verified=True,
            is_blocked=True,
        )
        self.akun_admin = User.objects.create_user(
            username='admin_utama',
            email='admin@kampus.ac.id',
            password='SandiAdmin123!',
            email_verified=True,
            is_staff=True,
        )

    def tearDown(self):
        cache.clear()

    def test_deteksi_email_sekali_pakai(self):
        self.assertTrue(apakah_email_sekali_pakai('uji@mailinator.com'))
        self.assertTrue(apakah_email_sekali_pakai('uji@sub.yopmail.com'))
        self.assertTrue(apakah_email_sekali_pakai('uji@TEMPMAIL.COM'))
        self.assertFalse(apakah_email_sekali_pakai('mahasiswa@ui.ac.id'))

    def test_daftar_menolak_email_sekali_pakai(self):
        respons = self.client.post(
            reverse('accounts:daftar'),
            {
                'username': 'pengguna_uji',
                'email': 'tes@mailinator.com',
                'password1': 'SandiAman123!',
                'password2': 'SandiAman123!',
            },
        )
        self.assertEqual(respons.status_code, 200)
        self.assertFalse(User.objects.filter(username='pengguna_uji').exists())
        self.assertContains(respons, 'Email sekali pakai')

    def test_daftar_berhasil_mengirim_email_verifikasi_dan_catat_ip(self):
        respons = self.client.post(
            reverse('accounts:daftar'),
            {
                'username': 'pengguna_baru',
                'email': 'baru@kampus.ac.id',
                'password1': 'SandiAman123!',
                'password2': 'SandiAman123!',
            },
            REMOTE_ADDR='203.0.113.10',
        )
        self.assertRedirects(respons, reverse('accounts:dasbor'))

        pengguna_baru = User.objects.get(username='pengguna_baru')
        self.assertFalse(pengguna_baru.email_verified)
        self.assertEqual(pengguna_baru.registration_ip, '203.0.113.10')
        self.assertEqual(pengguna_baru.last_ip, '203.0.113.10')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/akun/verifikasi-email/', mail.outbox[0].body)

    def test_verifikasi_email_valid_dan_token_palsu(self):
        token_valid = buat_token_verifikasi_email(self.pengguna_belum_verifikasi)
        respons_valid = self.client.get(
            reverse('accounts:verifikasi_email', kwargs={'token': token_valid})
        )
        self.assertEqual(respons_valid.status_code, 200)
        self.pengguna_belum_verifikasi.refresh_from_db()
        self.assertTrue(self.pengguna_belum_verifikasi.email_verified)

        respons_palsu = self.client.get(
            reverse('accounts:verifikasi_email', kwargs={'token': 'token-tidak-valid'})
        )
        self.assertEqual(respons_palsu.status_code, 200)
        self.assertContains(respons_palsu, 'tidak valid')

    def test_kirim_ulang_verifikasi_dan_jeda_waktu(self):
        self.client.force_login(self.pengguna_belum_verifikasi)
        respons_pertama = self.client.post(reverse('accounts:kirim_ulang_verifikasi'))
        self.assertRedirects(respons_pertama, reverse('accounts:dasbor'))
        self.assertEqual(len(mail.outbox), 1)

        # Permintaan kedua langsung ditahan selama masa jeda
        respons_kedua = self.client.post(reverse('accounts:kirim_ulang_verifikasi'))
        self.assertRedirects(respons_kedua, reverse('accounts:dasbor'))
        self.assertEqual(len(mail.outbox), 1)

    def test_login_dengan_username_atau_email_dan_update_ip(self):
        respons = self.client.post(
            reverse('accounts:login'),
            {'pengenal': 'andi@kampus.ac.id', 'password': 'SandiKuat123!'},
            REMOTE_ADDR='198.51.100.25',
        )
        self.assertRedirects(respons, reverse('accounts:dasbor'))
        self.pengguna_biasa.refresh_from_db()
        self.assertEqual(self.pengguna_biasa.last_ip, '198.51.100.25')

    def test_login_ditolak_jika_akun_diblokir(self):
        respons = self.client.post(
            reverse('accounts:login'),
            {'pengenal': 'citra_blokir', 'password': 'SandiKuat123!'},
        )
        self.assertEqual(respons.status_code, 403)
        self.assertContains(respons, 'diblokir', status_code=403)

    def test_pembatasan_percobaan_login_mengunci_setelah_5_kali_gagal(self):
        url_login = reverse('accounts:login')
        for _ in range(4):
            respons = self.client.post(
                url_login,
                {'pengenal': 'andi_user', 'password': 'salah'},
                REMOTE_ADDR='192.0.2.50',
            )
            self.assertEqual(respons.status_code, 200)

        respons_ke_5 = self.client.post(
            url_login,
            {'pengenal': 'andi_user', 'password': 'salah'},
            REMOTE_ADDR='192.0.2.50',
        )
        self.assertEqual(respons_ke_5.status_code, 429)

        # Percobaan berikutnya tetap ditolak meski password benar
        respons_terkunci = self.client.post(
            url_login,
            {'pengenal': 'andi_user', 'password': 'SandiKuat123!'},
            REMOTE_ADDR='192.0.2.50',
        )
        self.assertEqual(respons_terkunci.status_code, 429)

    def test_alur_reset_kata_sandi(self):
        respons_minta = self.client.post(
            reverse('accounts:lupa_sandi'),
            {'email': 'andi@kampus.ac.id'},
        )
        self.assertRedirects(respons_minta, reverse('accounts:lupa_sandi_terkirim'))
        self.assertEqual(len(mail.outbox), 1)

        cocok = re.search(r'/akun/reset-sandi/([^/]+)/([^/\s]+)/', mail.outbox[0].body)
        self.assertIsNotNone(cocok)
        uidb64, token = cocok.group(1), cocok.group(2)

        # Buka tautan reset terlebih dahulu agar Django mengarahkan ke URL set-password
        url_reset = reverse('accounts:reset_sandi_konfirmasi', kwargs={'uidb64': uidb64, 'token': token})
        respons_form = self.client.get(url_reset, follow=True)
        self.assertEqual(respons_form.status_code, 200)
        url_set_password = respons_form.request['PATH_INFO']

        respons_konfirmasi = self.client.post(
            url_set_password,
            {
                'new_password1': 'SandiBaruKuat99!',
                'new_password2': 'SandiBaruKuat99!',
            },
            follow=True,
        )
        self.assertEqual(respons_konfirmasi.status_code, 200)
        self.pengguna_biasa.refresh_from_db()
        self.assertTrue(self.pengguna_biasa.check_password('SandiBaruKuat99!'))

    def test_pembatasan_akses_tiga_peran(self):
        # 1. Pengunjung (belum login)
        self.assertEqual(tentukan_peran_pengguna(None), 'pengunjung')
        self.assertRedirects(self.client.get(reverse('accounts:dasbor')), reverse('accounts:login'))
        self.assertRedirects(self.client.get(reverse('accounts:panel_admin')), reverse('accounts:login'))
        self.assertEqual(self.client.get(reverse('accounts:hak_akses')).status_code, 200)

        # 2. Pengguna biasa
        self.assertEqual(tentukan_peran_pengguna(self.pengguna_biasa), 'pengguna')
        self.client.force_login(self.pengguna_biasa)
        self.assertEqual(self.client.get(reverse('accounts:dasbor')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('accounts:login')), reverse('accounts:dasbor'))
        self.assertRedirects(self.client.get(reverse('accounts:daftar')), reverse('accounts:dasbor'))
        self.assertEqual(self.client.get(reverse('accounts:panel_admin')).status_code, 403)

        # 3. Admin
        self.assertEqual(tentukan_peran_pengguna(self.akun_admin), 'admin')
        self.client.force_login(self.akun_admin)
        self.assertEqual(self.client.get(reverse('accounts:panel_admin')).status_code, 200)

    def test_pengguna_diblokir_saat_sesi_aktif_ditolak(self):
        self.client.force_login(self.pengguna_diblokir)
        respons = self.client.get(reverse('accounts:dasbor'))
        self.assertEqual(respons.status_code, 403)
