from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.forms import FormLogin, FormLupaSandi, FormPendaftaran, FormSetelSandiBaru
from accounts.permissions import tentukan_peran_pengguna, wajib_admin, wajib_pengguna, wajib_pengunjung
from accounts.utils import (
    ambil_ip_klien,
    boleh_kirim_ulang_verifikasi,
    catat_kegagalan_login,
    cek_batas_percobaan_login,
    kirim_email_verifikasi,
    reset_kegagalan_login,
    validasi_token_verifikasi_email,
)
from core.points import compute_score

User = get_user_model()


# Matriks hak akses tiga peran untuk ditampilkan di halaman /akun/hak-akses/
MATRIKS_HAK_AKSES = [
    {
        'fitur': 'Melihat halaman login, daftar, & lupa sandi',
        'pengunjung': 'Ya',
        'pengguna_belum_verifikasi': 'Dialihkan ke Dasbor',
        'pengguna_terverifikasi': 'Dialihkan ke Dasbor',
        'admin': 'Dialihkan ke Dasbor',
    },
    {
        'fitur': 'Mengisi kuesioner publik (allow_anonymous=True)',
        'pengunjung': 'Ya (tanpa poin)',
        'pengguna_belum_verifikasi': 'Ya (tanpa poin)',
        'pengguna_terverifikasi': 'Ya (dapat poin)',
        'admin': 'Ya (dapat poin)',
    },
    {
        'fitur': 'Mengisi kuesioner khusus akun (allow_anonymous=False)',
        'pengunjung': 'Ditolak (wajib login)',
        'pengguna_belum_verifikasi': 'Ya (tanpa poin)',
        'pengguna_terverifikasi': 'Ya (dapat poin)',
        'admin': 'Ya (dapat poin)',
    },
    {
        'fitur': 'Mengakses Dasbor Akun & kirim ulang verifikasi email',
        'pengunjung': 'Ditolak (ke Login)',
        'pengguna_belum_verifikasi': 'Ya',
        'pengguna_terverifikasi': 'Ya',
        'admin': 'Ya',
    },
    {
        'fitur': 'Membuat & menerbitkan kuesioner',
        'pengunjung': 'Ditolak (ke Login)',
        'pengguna_belum_verifikasi': 'Ditolak (wajib verifikasi)',
        'pengguna_terverifikasi': 'Ya',
        'admin': 'Ya',
    },
    {
        'fitur': 'Melaporkan kuesioner bermasalah',
        'pengunjung': 'Ditolak (ke Login)',
        'pengguna_belum_verifikasi': 'Ditolak (wajib verifikasi)',
        'pengguna_terverifikasi': 'Ya',
        'admin': 'Ya',
    },
    {
        'fitur': 'Mengakses Panel Admin (/akun/panel-admin/ & /admin/)',
        'pengunjung': 'Ditolak (ke Login)',
        'pengguna_belum_verifikasi': 'Ditolak (403 Forbidden)',
        'pengguna_terverifikasi': 'Ditolak (403 Forbidden)',
        'admin': 'Ya',
    },
]


@wajib_pengunjung
def daftar_pengguna(request):
    """Menangani pendaftaran akun baru dan pengiriman email verifikasi."""
    if request.method == 'POST':
        form_daftar = FormPendaftaran(request.POST)
        if form_daftar.is_valid():
            ip_klien = ambil_ip_klien(request)
            pengguna_baru = form_daftar.save(commit=False)
            pengguna_baru.email = form_daftar.cleaned_data['email']
            pengguna_baru.email_verified = False
            pengguna_baru.registration_ip = ip_klien
            pengguna_baru.last_ip = ip_klien
            pengguna_baru.save()

            kirim_email_verifikasi(request, pengguna_baru)
            login(request, pengguna_baru)
            messages.success(
                request,
                'Akun berhasil dibuat. Silakan cek email Anda untuk memverifikasi akun.',
            )
            return redirect('accounts:dasbor')
    else:
        form_daftar = FormPendaftaran()

    return render(
        request,
        'accounts/daftar.html',
        {'form_daftar': form_daftar},
    )


@wajib_pengunjung
def login_pengguna(request):
    """Menangani login dengan pembatasan percobaan gagal dan pengecekan status blokir."""
    pesan_error = ''
    status_http = 200
    tujuan_berikutnya = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        form_login = FormLogin(request.POST)
        if form_login.is_valid():
            pengenal = form_login.cleaned_data['pengenal'].strip()
            kata_sandi = form_login.cleaned_data['password']
            ip_klien = ambil_ip_klien(request)

            # Periksa apakah IP atau akun sedang terkena batas percobaan login
            apakah_terkunci, _ = cek_batas_percobaan_login(ip_klien, pengenal)
            if apakah_terkunci:
                pesan_error = (
                    'Terlalu banyak percobaan login yang gagal. '
                    'Silakan tunggu 15 menit sebelum mencoba lagi.'
                )
                status_http = 429
            else:
                # Izinkan login menggunakan email maupun username
                username_untuk_auth = pengenal
                if '@' in pengenal:
                    pengguna_berdasarkan_email = User.objects.filter(email__iexact=pengenal).first()
                    if pengguna_berdasarkan_email is not None:
                        username_untuk_auth = pengguna_berdasarkan_email.username

                pengguna = authenticate(
                    request,
                    username=username_untuk_auth,
                    password=kata_sandi,
                )

                if pengguna is None:
                    catat_kegagalan_login(ip_klien, pengenal)
                    terkunci_sekarang, sisa = cek_batas_percobaan_login(ip_klien, pengenal)
                    if terkunci_sekarang:
                        pesan_error = (
                            'Terlalu banyak percobaan login yang gagal. '
                            'Akun dikunci sementara selama 15 menit.'
                        )
                        status_http = 429
                    else:
                        pesan_error = (
                            f'Username/email atau kata sandi salah. '
                            f'Sisa percobaan sebelum dikunci: {sisa} kali.'
                        )
                elif pengguna.is_blocked:
                    pesan_error = 'Akun Anda telah diblokir oleh admin dan tidak dapat masuk.'
                    status_http = 403
                else:
                    reset_kegagalan_login(ip_klien, pengenal)
                    login(request, pengguna)
                    pengguna.last_ip = ip_klien
                    pengguna.save(update_fields=['last_ip'])

                    # Validasi URL tujuan agar aman dari open redirect
                    if tujuan_berikutnya and url_has_allowed_host_and_scheme(
                        tujuan_berikutnya,
                        allowed_hosts={request.get_host()},
                        require_https=request.is_secure(),
                    ):
                        return redirect(tujuan_berikutnya)
                    return redirect('accounts:dasbor')
    else:
        form_login = FormLogin()

    return render(
        request,
        'accounts/login.html',
        {
            'form_login': form_login,
            'pesan_error': pesan_error,
            'tujuan_berikutnya': tujuan_berikutnya,
        },
        status=status_http,
    )


@require_POST
def logout_pengguna(request):
    """Mengeluarkan pengguna dari sesi aktif melalui metode POST."""
    logout(request)
    messages.info(request, 'Anda telah keluar dari akun.')
    return redirect('accounts:login')


def verifikasi_email(request, token):
    """Memvalidasi token verifikasi email dan menandai akun sebagai terverifikasi."""
    id_pengguna, email_token = validasi_token_verifikasi_email(token)
    berhasil = False
    pesan_hasil = 'Tautan verifikasi tidak valid atau sudah kedaluwarsa.'

    if id_pengguna is not None:
        pengguna = User.objects.filter(pk=id_pengguna).first()
        if pengguna is not None and pengguna.email.lower() == email_token:
            if not pengguna.email_verified:
                pengguna.email_verified = True
                pengguna.save(update_fields=['email_verified'])
            berhasil = True
            pesan_hasil = 'Alamat email Anda berhasil diverifikasi. Seluruh fitur pengguna kini aktif.'

    return render(
        request,
        'accounts/verifikasi_email.html',
        {
            'berhasil': berhasil,
            'pesan_hasil': pesan_hasil,
        },
    )


@require_POST
@wajib_pengguna()
def kirim_ulang_verifikasi(request):
    """Mengirim ulang tautan verifikasi email untuk pengguna yang belum terverifikasi."""
    if request.user.email_verified:
        messages.info(request, 'Alamat email Anda sudah terverifikasi.')
        return redirect('accounts:dasbor')

    if not boleh_kirim_ulang_verifikasi(request.user.pk):
        messages.warning(
            request,
            'Tunggu 1 menit sebelum meminta pengiriman ulang email verifikasi.',
        )
        return redirect('accounts:dasbor')

    kirim_email_verifikasi(request, request.user)
    messages.success(request, 'Tautan verifikasi baru telah dikirim ke email Anda.')
    return redirect('accounts:dasbor')


@wajib_pengguna()
def dasbor_pengguna(request):
    """Menampilkan ringkasan profil, peran, status verifikasi, dan skor poin pengguna."""
    peran_pengguna = tentukan_peran_pengguna(request.user)
    total_poin = compute_score(request.user)

    return render(
        request,
        'accounts/dasbor.html',
        {
            'peran_pengguna': peran_pengguna,
            'total_poin': total_poin,
        },
    )


@wajib_admin
def panel_admin(request):
    """Menampilkan halaman ringkasan khusus peran Admin untuk moderasi akun."""
    total_pengguna = User.objects.count()
    pengguna_terverifikasi = User.objects.filter(email_verified=True).count()
    pengguna_diblokir = User.objects.filter(is_blocked=True).count()
    total_admin = User.objects.filter(is_staff=True).count()
    daftar_pengguna_terbaru = User.objects.order_by('-date_joined')[:10]

    return render(
        request,
        'accounts/panel_admin.html',
        {
            'total_pengguna': total_pengguna,
            'pengguna_terverifikasi': pengguna_terverifikasi,
            'pengguna_diblokir': pengguna_diblokir,
            'total_admin': total_admin,
            'daftar_pengguna_terbaru': daftar_pengguna_terbaru,
        },
    )


def tabel_hak_akses(request):
    """Menampilkan tabel matriks hak akses untuk ketiga peran (Pengunjung, Pengguna, Admin)."""
    peran_saat_ini = tentukan_peran_pengguna(request.user)
    return render(
        request,
        'accounts/hak_akses.html',
        {
            'matriks_hak_akses': MATRIKS_HAK_AKSES,
            'peran_saat_ini': peran_saat_ini,
        },
    )


class LupaSandiView(PasswordResetView):
    """Halaman permintaan reset kata sandi."""

    template_name = 'accounts/lupa_sandi.html'
    form_class = FormLupaSandi
    email_template_name = 'accounts/email_reset_sandi.txt'
    subject_template_name = 'accounts/subjek_reset_sandi.txt'
    success_url = reverse_lazy('accounts:lupa_sandi_terkirim')


class LupaSandiTerkirimView(PasswordResetDoneView):
    """Halaman konfirmasi setelah permintaan reset kata sandi dikirim."""

    template_name = 'accounts/lupa_sandi_terkirim.html'


class KonfirmasiResetSandiView(PasswordResetConfirmView):
    """Halaman pengisian kata sandi baru dari tautan email."""

    template_name = 'accounts/reset_sandi_konfirmasi.html'
    form_class = FormSetelSandiBaru
    success_url = reverse_lazy('accounts:reset_sandi_selesai')


class ResetSandiSelesaiView(PasswordResetCompleteView):
    """Halaman pemberitahuan bahwa kata sandi berhasil diubah."""

    template_name = 'accounts/reset_sandi_selesai.html'
