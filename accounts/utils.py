from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse

# Daftar domain email sekali pakai (disposable email) yang diblokir saat pendaftaran
DOMAIN_EMAIL_SEKALI_PAKAI = {
    '10minutemail.com',
    '33mail.com',
    'anonbox.net',
    'binkmail.com',
    'bobmail.info',
    'burnermail.io',
    'chammy.info',
    'devnullmail.com',
    'discard.email',
    'dispostable.com',
    'dodgit.com',
    'e4ward.com',
    'emailondeck.com',
    'fakeinbox.com',
    'filzmail.com',
    'getnada.com',
    'gishpuppy.com',
    'grr.la',
    'guerrillamail.com',
    'guerrillamailblock.com',
    'hidzz.com',
    'incognitomail.org',
    'jetable.org',
    'kasmail.com',
    'koszmail.pl',
    'kurzepost.de',
    'lortemail.dk',
    'mailcatch.com',
    'maildrop.cc',
    'mailexpire.com',
    'mailin8r.com',
    'mailinator.com',
    'mailme.lv',
    'mailmoat.com',
    'mailnesia.com',
    'meltmail.com',
    'messagebeamer.de',
    'mintemail.com',
    'mohmal.com',
    'mytemp.email',
    'nervmich.net',
    'nervtmich.net',
    'no-spam.ws',
    'nomail.xl.cx',
    'nospam.ze.tc',
    'owlpic.com',
    'pookmail.com',
    'quickinbox.com',
    'rcpt.at',
    'recode.me',
    'rtrtr.com',
    'safe-mail.net',
    'saynotospams.com',
    'selfdestructingmail.com',
    'sendspamhere.com',
    'sharklasers.com',
    'shiftmail.com',
    'skeefmail.com',
    'slopsbox.com',
    'smellfear.com',
    'snakemail.com',
    'sneakemail.com',
    'sogetthis.com',
    'soodonims.com',
    'spambob.com',
    'spambog.com',
    'spambox.us',
    'spamcero.com',
    'spamcon.org',
    'spamcorptastic.com',
    'spamcowboy.com',
    'spamday.com',
    'spamex.com',
    'spamfree24.org',
    'spamgourmet.com',
    'spamhole.com',
    'spamify.com',
    'spaminator.de',
    'spamkill.info',
    'spaml.com',
    'spammotel.com',
    'spamobox.com',
    'spamoff.de',
    'spamslicer.com',
    'spamspot.com',
    'spamthis.co.uk',
    'superrito.com',
    'suremail.info',
    'teleworm.us',
    'temp-mail.org',
    'tempail.com',
    'tempemail.net',
    'tempinbox.com',
    'tempmail.com',
    'tempr.email',
    'thankyou2010.com',
    'thisisnotmyrealemail.com',
    'throwawaymail.com',
    'tradermail.info',
    'trash-mail.at',
    'trash2009.com',
    'trashemail.de',
    'trashmail.com',
    'trashymail.com',
    'tyldd.com',
    'uggsrock.com',
    'wegwerfmail.de',
    'wh4f.org',
    'whyspam.me',
    'willselfdestruct.com',
    'xagloo.com',
    'xemaps.com',
    'xents.com',
    'xmaily.com',
    'xoxy.net',
    'yapped.net',
    'yep.it',
    'yogamaven.com',
    'yopmail.com',
    'yuurok.com',
    'zehnminuten.de',
    'zippymail.info',
    'zoemail.org',
}

# Batas percobaan login gagal sebelum dikunci sementara
BATAS_PERCOBAAN_LOGIN = 5
DURASI_KUNCI_LOGIN_DETIK = 900  # 15 menit
MASA_BERLAKU_TOKEN_VERIFIKASI_DETIK = 86400  # 24 jam
JEDA_KIRIM_ULANG_VERIFIKASI_DETIK = 60  # 1 menit


def ambil_ip_klien(request):
    """Ambil alamat IP klien dari header X-Forwarded-For atau REMOTE_ADDR."""
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def apakah_email_sekali_pakai(alamat_email):
    """Periksa apakah domain email termasuk layanan email sekali pakai (disposable)."""
    if not alamat_email or '@' not in alamat_email:
        return False

    domain_email = alamat_email.rsplit('@', 1)[1].strip().lower()
    if domain_email in DOMAIN_EMAIL_SEKALI_PAKAI:
        return True

    # Blokir juga subdomain dari domain email sekali pakai
    for domain_terlarang in DOMAIN_EMAIL_SEKALI_PAKAI:
        if domain_email.endswith('.' + domain_terlarang):
            return True

    return False


def _kunci_cache_login(ip_klien, pengenal_akun):
    """Buat kunci cache unik untuk melacak percobaan login berdasarkan IP dan akun."""
    pengenal_bersih = (pengenal_akun or '').strip().lower()
    ip_bersih = ip_klien or 'unknown'
    return f'batas_login:{ip_bersih}:{pengenal_bersih}'


def cek_batas_percobaan_login(ip_klien, pengenal_akun):
    """Periksa apakah percobaan login sedang terkunci dan kembalikan sisa percobaan."""
    kunci_ip = _kunci_cache_login(ip_klien, 'ip_global')
    kunci_akun = _kunci_cache_login(ip_klien, pengenal_akun)

    jumlah_gagal_ip = cache.get(kunci_ip, 0)
    jumlah_gagal_akun = cache.get(kunci_akun, 0)
    jumlah_tertinggi = max(jumlah_gagal_ip, jumlah_gagal_akun)

    apakah_terkunci = jumlah_tertinggi >= BATAS_PERCOBAAN_LOGIN
    sisa_percobaan = max(0, BATAS_PERCOBAAN_LOGIN - jumlah_tertinggi)
    return apakah_terkunci, sisa_percobaan


def catat_kegagalan_login(ip_klien, pengenal_akun):
    """Tambah hitungan percobaan login gagal ke cache dengan batas waktu kunci."""
    for kunci in (
        _kunci_cache_login(ip_klien, 'ip_global'),
        _kunci_cache_login(ip_klien, pengenal_akun),
    ):
        jumlah_saat_ini = cache.get(kunci, 0)
        cache.set(kunci, jumlah_saat_ini + 1, timeout=DURASI_KUNCI_LOGIN_DETIK)


def reset_kegagalan_login(ip_klien, pengenal_akun):
    """Hapus catatan kegagalan login setelah pengguna berhasil masuk."""
    cache.delete(_kunci_cache_login(ip_klien, 'ip_global'))
    cache.delete(_kunci_cache_login(ip_klien, pengenal_akun))


def buat_token_verifikasi_email(pengguna):
    """Buat token bertanda tangan dengan masa berlaku 24 jam untuk verifikasi email."""
    signer = TimestampSigner(salt='verifikasi-email-akun')
    muatan = f'{pengguna.pk}:{pengguna.email.lower()}'
    return signer.sign(muatan)


def validasi_token_verifikasi_email(token):
    """Validasi token verifikasi email dan kembalikan tuple (user_id, email) atau (None, None)."""
    signer = TimestampSigner(salt='verifikasi-email-akun')
    try:
        muatan = signer.unsign(token, max_age=MASA_BERLAKU_TOKEN_VERIFIKASI_DETIK)
        id_str, email_token = muatan.split(':', 1)
        return int(id_str), email_token
    except (BadSignature, SignatureExpired, ValueError):
        return None, None


def kirim_email_verifikasi(request, pengguna):
    """Kirim tautan verifikasi email ke alamat email pengguna."""
    token = buat_token_verifikasi_email(pengguna)
    jalur_verifikasi = reverse('accounts:verifikasi_email', kwargs={'token': token})
    tautan_lengkap = request.build_absolute_uri(jalur_verifikasi)

    subjek = 'Verifikasi Email Akun Respondent Exchanger'
    isi_pesan = (
        f'Halo {pengguna.username},\n\n'
        'Silakan buka tautan berikut untuk memverifikasi alamat email Anda '
        '(berlaku selama 24 jam):\n\n'
        f'{tautan_lengkap}\n\n'
        'Jika Anda tidak mendaftar di Respondent Exchanger, abaikan email ini.\n'
    )

    send_mail(
        subject=subjek,
        message=isi_pesan,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[pengguna.email],
        fail_silently=False,
    )


def boleh_kirim_ulang_verifikasi(pengguna_id):
    """Batasi frekuensi pengiriman ulang email verifikasi agar tidak disalahgunakan."""
    kunci = f'jeda_verifikasi:{pengguna_id}'
    if cache.get(kunci):
        return False
    cache.set(kunci, True, timeout=JEDA_KIRIM_ULANG_VERIFIKASI_DETIK)
    return True
