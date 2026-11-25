from django.db.models import Sum

from core.models import PointLedger


def compute_score(pengguna):
    """Hitung total skor poin aktif milik pengguna dari buku besar poin."""
    # Pengguna anonim atau belum login tidak memiliki skor poin
    if pengguna is None or not getattr(pengguna, 'is_authenticated', False):
        return 0

    # Jumlahkan hanya entri poin yang belum dicabut oleh admin
    hasil_agregasi = PointLedger.objects.filter(
        user=pengguna,
        is_revoked=False,
    ).aggregate(total_poin=Sum('points'))

    total_poin = hasil_agregasi.get('total_poin')
    if total_poin is None:
        return 0
    return int(total_poin)


def tentukan_kelayakan_poin(kuesioner, responden, apakah_terlalu_cepat, jumlah_pertanyaan):
    """Tentukan apakah responden berhak mendapat poin beserta jumlah poinnya."""
    # Pengisian yang terlalu cepat tidak dihitung dan tidak mendapat poin
    if apakah_terlalu_cepat:
        return False, 0

    # Pengisi anonim tidak mendapat poin
    if responden is None or not getattr(responden, 'is_authenticated', False):
        return False, 0

    # Pengguna yang belum verifikasi email atau diblokir tidak mendapat poin
    if not responden.email_verified or responden.is_blocked:
        return False, 0

    # Pemilik kuesioner tidak mendapat poin dari kuesionernya sendiri
    if responden.id == kuesioner.owner_id:
        return False, 0

    # Jumlah poin mengikuti jumlah pertanyaan kuesioner (dibatasi 1 sampai 20)
    jumlah_poin = min(20, max(1, jumlah_pertanyaan))
    return True, jumlah_poin


def catat_poin_ke_buku_besar(pengguna, kuesioner, respons, jumlah_poin):
    """Catat perolehan poin responden ke tabel buku besar poin (append-only)."""
    if jumlah_poin <= 0:
        return None

    entri_poin = PointLedger.objects.create(
        user=pengguna,
        questionnaire=kuesioner,
        response=respons,
        points=jumlah_poin,
    )
    return entri_poin
