from django.urls import path

from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('daftar/', views.daftar_pengguna, name='daftar'),
    path('login/', views.login_pengguna, name='login'),
    path('logout/', views.logout_pengguna, name='logout'),
    path('verifikasi-email/<str:token>/', views.verifikasi_email, name='verifikasi_email'),
    path('kirim-ulang-verifikasi/', views.kirim_ulang_verifikasi, name='kirim_ulang_verifikasi'),
    path('dasbor/', views.dasbor_pengguna, name='dasbor'),
    path('panel-admin/', views.panel_admin, name='panel_admin'),
    path('hak-akses/', views.tabel_hak_akses, name='hak_akses'),
    path('lupa-sandi/', views.LupaSandiView.as_view(), name='lupa_sandi'),
    path('lupa-sandi/terkirim/', views.LupaSandiTerkirimView.as_view(), name='lupa_sandi_terkirim'),
    path(
        'reset-sandi/<uidb64>/<token>/',
        views.KonfirmasiResetSandiView.as_view(),
        name='reset_sandi_konfirmasi',
    ),
    path(
        'reset-sandi/selesai/',
        views.ResetSandiSelesaiView.as_view(),
        name='reset_sandi_selesai',
    ),
]
