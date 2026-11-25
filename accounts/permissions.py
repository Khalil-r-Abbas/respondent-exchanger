from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def tentukan_peran_pengguna(pengguna):
    """Tentukan peran aktif pengguna: pengunjung, pengguna, atau admin."""
    if pengguna is None or not getattr(pengguna, 'is_authenticated', False):
        return 'pengunjung'
    if getattr(pengguna, 'is_staff', False) or getattr(pengguna, 'is_superuser', False):
        return 'admin'
    return 'pengguna'


def wajib_pengunjung(fungsi_view):
    """Batasi halaman hanya untuk pengunjung yang belum login (login/daftar)."""

    @wraps(fungsi_view)
    def pembungkus(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dasbor')
        return fungsi_view(request, *args, **kwargs)

    return pembungkus


def wajib_pengguna(perlu_verifikasi_email=False):
    """Batasi halaman untuk pengguna yang sudah login, tidak diblokir, dan opsional terverifikasi."""

    def dekorator(fungsi_view):
        @wraps(fungsi_view)
        def pembungkus(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.info(request, 'Silakan masuk terlebih dahulu untuk mengakses halaman tersebut.')
                return redirect('accounts:login')

            # Jika akun diblokir admin saat sesi masih aktif, keluarkan paksa dan tolak akses
            if getattr(request.user, 'is_blocked', False):
                logout(request)
                raise PermissionDenied('Akun Anda telah diblokir oleh admin.')

            if perlu_verifikasi_email and not getattr(request.user, 'email_verified', False):
                messages.warning(
                    request,
                    'Fitur ini hanya tersedia setelah Anda memverifikasi alamat email.',
                )
                return redirect('accounts:dasbor')

            return fungsi_view(request, *args, **kwargs)

        return pembungkus

    return dekorator


def wajib_admin(fungsi_view):
    """Batasi halaman khusus untuk peran Admin (is_staff atau is_superuser)."""

    @wraps(fungsi_view)
    def pembungkus(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, 'Silakan masuk sebagai admin untuk mengakses halaman tersebut.')
            return redirect('accounts:login')

        if getattr(request.user, 'is_blocked', False):
            logout(request)
            raise PermissionDenied('Akun Anda telah diblokir oleh admin.')

        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied('Halaman ini hanya dapat diakses oleh Admin.')

        return fungsi_view(request, *args, **kwargs)

    return pembungkus
