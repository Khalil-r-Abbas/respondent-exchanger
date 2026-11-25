import uuid

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.points import (
    catat_poin_ke_buku_besar,
    compute_score,
    tentukan_kelayakan_poin,
)
from forms_app.models import Answer, Question, Questionnaire, Response, SubmissionSession


NAMA_SESSION_ANONIM = 'kunci_anonim_responden'


def _ambil_atau_buat_kunci_anonim(request):
    """Ambil kunci unik pengisi anonim dari session, atau buat baru jika belum ada."""
    kunci_anonim = request.session.get(NAMA_SESSION_ANONIM, '')
    if not kunci_anonim:
        kunci_anonim = uuid.uuid4().hex
        request.session[NAMA_SESSION_ANONIM] = kunci_anonim
    return kunci_anonim


def _cek_sudah_pernah_mengisi(kuesioner, pengguna, kunci_anonim):
    """Periksa apakah pengguna atau kunci anonim sudah pernah mengirim respons."""
    if pengguna.is_authenticated:
        return Response.objects.filter(
            questionnaire=kuesioner,
            respondent=pengguna,
        ).exists()

    if kunci_anonim:
        return Response.objects.filter(
            questionnaire=kuesioner,
            anonymous_key=kunci_anonim,
        ).exists()

    return False


def _ambil_atau_buat_sesi(kuesioner, pengguna, kunci_anonim):
    """Ambil sesi pengisian aktif dari server, atau buat sesi baru dengan waktu mulai server."""
    waktu_sekarang = timezone.now()

    if pengguna.is_authenticated:
        sesi = SubmissionSession.objects.filter(
            questionnaire=kuesioner,
            user=pengguna,
            status=SubmissionSession.SessionStatus.ACTIVE,
        ).first()
    else:
        sesi = SubmissionSession.objects.filter(
            questionnaire=kuesioner,
            user__isnull=True,
            anonymous_key=kunci_anonim,
            status=SubmissionSession.SessionStatus.ACTIVE,
        ).first()

    # Jika belum ada sesi aktif, catat waktu mulai baru dari jam server
    if sesi is None:
        sesi = SubmissionSession.objects.create(
            questionnaire=kuesioner,
            user=pengguna if pengguna.is_authenticated else None,
            anonymous_key='' if pengguna.is_authenticated else kunci_anonim,
            started_at=waktu_sekarang,
            last_activity_at=waktu_sekarang,
            status=SubmissionSession.SessionStatus.ACTIVE,
        )
    else:
        sesi.last_activity_at = waktu_sekarang
        sesi.save(update_fields=['last_activity_at'])

    return sesi


def _hitung_sisa_detik_server(sesi, batas_waktu_minimum):
    """Hitung sisa waktu minimum (detik) berdasarkan waktu mulai di server."""
    durasi_berjalan = int((timezone.now() - sesi.started_at).total_seconds())
    sisa_detik = batas_waktu_minimum - durasi_berjalan
    if sisa_detik < 0:
        return 0
    return sisa_detik


def _validasi_semua_jawaban(daftar_pertanyaan, data_post):
    """Validasi seluruh jawaban sesuai tipe pertanyaan dan status wajib."""
    daftar_error = {}
    jawaban_tervalidasi = {}
    jawaban_tersimpan = {}

    for pertanyaan in daftar_pertanyaan:
        nama_field = f'pertanyaan_{pertanyaan.id}'
        tipe = pertanyaan.question_type

        if tipe == Question.QuestionType.MULTIPLE_CHOICE:
            nilai_mentah = data_post.getlist(nama_field)
            jawaban_tersimpan[pertanyaan.id] = nilai_mentah

            if pertanyaan.is_required and len(nilai_mentah) == 0:
                daftar_error[pertanyaan.id] = 'Pilih minimal satu jawaban.'
                continue

            # Pastikan semua opsi yang dipilih benar-benar ada di daftar opsi pertanyaan
            opsi_valid = set(pertanyaan.options or [])
            if any(item not in opsi_valid for item in nilai_mentah):
                daftar_error[pertanyaan.id] = 'Pilihan tidak valid.'
                continue

            jawaban_tervalidasi[pertanyaan.id] = nilai_mentah

        elif tipe in (Question.QuestionType.SINGLE_CHOICE, Question.QuestionType.DROPDOWN):
            nilai_mentah = data_post.get(nama_field, '').strip()
            jawaban_tersimpan[pertanyaan.id] = nilai_mentah

            if pertanyaan.is_required and not nilai_mentah:
                daftar_error[pertanyaan.id] = 'Pertanyaan ini wajib diisi.'
                continue

            if nilai_mentah and nilai_mentah not in (pertanyaan.options or []):
                daftar_error[pertanyaan.id] = 'Pilihan tidak valid.'
                continue

            jawaban_tervalidasi[pertanyaan.id] = nilai_mentah if nilai_mentah else None

        elif tipe == Question.QuestionType.RATING:
            nilai_mentah = data_post.get(nama_field, '').strip()
            jawaban_tersimpan[pertanyaan.id] = nilai_mentah

            if pertanyaan.is_required and not nilai_mentah:
                daftar_error[pertanyaan.id] = 'Pilih nilai rating.'
                continue

            if not nilai_mentah:
                jawaban_tervalidasi[pertanyaan.id] = None
                continue

            try:
                angka_rating = int(nilai_mentah)
            except ValueError:
                daftar_error[pertanyaan.id] = 'Rating harus berupa angka.'
                continue

            if angka_rating < 1 or angka_rating > pertanyaan.rating_max:
                daftar_error[pertanyaan.id] = f'Rating harus antara 1 sampai {pertanyaan.rating_max}.'
                continue

            jawaban_tervalidasi[pertanyaan.id] = angka_rating

        else:
            # Tipe short_text atau long_text
            nilai_mentah = data_post.get(nama_field, '').strip()
            jawaban_tersimpan[pertanyaan.id] = nilai_mentah

            if pertanyaan.is_required and not nilai_mentah:
                daftar_error[pertanyaan.id] = 'Pertanyaan ini wajib diisi.'
                continue

            jawaban_tervalidasi[pertanyaan.id] = nilai_mentah

    return jawaban_tervalidasi, jawaban_tersimpan, daftar_error


def isi_kuesioner(request, link_code):
    """Menampilkan halaman pengisian kuesioner dan memproses pengiriman respons."""
    kuesioner = get_object_or_404(Questionnaire, link_code=link_code)

    # Pastikan kuesioner masih berstatus terbit dan belum kedaluwarsa
    if not kuesioner.is_open:
        return render(
            request,
            'forms_app/isi_kuesioner.html',
            {
                'kuesioner': kuesioner,
                'status_akses': 'tutup',
            },
        )

    # Tolak pengisi anonim jika kuesioner mewajibkan login
    if not kuesioner.allow_anonymous and not request.user.is_authenticated:
        return render(
            request,
            'forms_app/isi_kuesioner.html',
            {
                'kuesioner': kuesioner,
                'status_akses': 'wajib_login',
            },
        )

    kunci_anonim = ''
    if not request.user.is_authenticated:
        kunci_anonim = _ambil_atau_buat_kunci_anonim(request)

    # Cegah pengisian ulang jika sudah pernah mengirim respons
    if _cek_sudah_pernah_mengisi(kuesioner, request.user, kunci_anonim):
        return render(
            request,
            'forms_app/isi_kuesioner.html',
            {
                'kuesioner': kuesioner,
                'status_akses': 'sudah_mengisi',
            },
        )

    daftar_pertanyaan = list(kuesioner.questions.order_by('order', 'id'))
    jumlah_pertanyaan = len(daftar_pertanyaan)
    batas_waktu_minimum = jumlah_pertanyaan * kuesioner.seconds_per_question
    sesi_pengisian = _ambil_atau_buat_sesi(kuesioner, request.user, kunci_anonim)

    daftar_error = {}
    jawaban_tersimpan = {}

    if request.method == 'POST':
        jawaban_tervalidasi, jawaban_tersimpan, daftar_error = _validasi_semua_jawaban(
            daftar_pertanyaan,
            request.POST,
        )

        if not daftar_error:
            waktu_kirim = timezone.now()
            durasi_detik = max(0, int((waktu_kirim - sesi_pengisian.started_at).total_seconds()))

            # Cek di server apakah pengisi mengirim lebih cepat dari waktu minimum
            apakah_terlalu_cepat = durasi_detik < batas_waktu_minimum

            berhak_poin, poin_didapat = tentukan_kelayakan_poin(
                kuesioner=kuesioner,
                responden=request.user,
                apakah_terlalu_cepat=apakah_terlalu_cepat,
                jumlah_pertanyaan=jumlah_pertanyaan,
            )

            try:
                with transaction.atomic():
                    respons_baru = Response.objects.create(
                        questionnaire=kuesioner,
                        respondent=request.user if request.user.is_authenticated else None,
                        anonymous_key='' if request.user.is_authenticated else kunci_anonim,
                        started_at=sesi_pengisian.started_at,
                        submitted_at=waktu_kirim,
                        duration_seconds=durasi_detik,
                        is_too_fast=apakah_terlalu_cepat,
                        is_counted=berhak_poin,
                        points_awarded=poin_didapat,
                    )

                    # Simpan setiap jawaban ke tabel forms_answer
                    daftar_objek_jawaban = []
                    for pertanyaan in daftar_pertanyaan:
                        daftar_objek_jawaban.append(
                            Answer(
                                response=respons_baru,
                                question=pertanyaan,
                                value=jawaban_tervalidasi.get(pertanyaan.id),
                            )
                        )
                    Answer.objects.bulk_create(daftar_objek_jawaban)

                    # Tutup sesi pengisian agar tidak dapat dipakai ulang
                    sesi_pengisian.status = SubmissionSession.SessionStatus.SUBMITTED
                    sesi_pengisian.last_activity_at = waktu_kirim
                    sesi_pengisian.save(update_fields=['status', 'last_activity_at'])

                    # Catat ke buku besar poin jika memenuhi seluruh syarat validitas
                    if berhak_poin:
                        catat_poin_ke_buku_besar(
                            pengguna=request.user,
                            kuesioner=kuesioner,
                            respons=respons_baru,
                            jumlah_poin=poin_didapat,
                        )
            except IntegrityError:
                return render(
                    request,
                    'forms_app/isi_kuesioner.html',
                    {
                        'kuesioner': kuesioner,
                        'status_akses': 'sudah_mengisi',
                    },
                )

            request.session['id_respons_terakhir'] = respons_baru.id
            return redirect('selesai_pengisian', link_code=kuesioner.link_code)

    sisa_detik = _hitung_sisa_detik_server(sesi_pengisian, batas_waktu_minimum)

    # Susun data per pertanyaan agar mudah dirender di template tanpa filter tambahan
    daftar_baris_pertanyaan = []
    for pertanyaan in daftar_pertanyaan:
        daftar_baris_pertanyaan.append({
            'pertanyaan': pertanyaan,
            'nilai': jawaban_tersimpan.get(pertanyaan.id, ''),
            'error': daftar_error.get(pertanyaan.id, ''),
            'daftar_rating': range(1, pertanyaan.rating_max + 1),
        })

    context = {
        'kuesioner': kuesioner,
        'status_akses': 'bisa_isi',
        'daftar_baris_pertanyaan': daftar_baris_pertanyaan,
        'jumlah_pertanyaan': jumlah_pertanyaan,
        'sesi_pengisian': sesi_pengisian,
        'batas_waktu_minimum': batas_waktu_minimum,
        'sisa_detik': sisa_detik,
        'ada_error': bool(daftar_error),
    }
    return render(request, 'forms_app/isi_kuesioner.html', context)


def selesai_pengisian(request, link_code):
    """Menampilkan ringkasan setelah respons disimpan, peringatan terlalu cepat, dan skor poin."""
    kuesioner = get_object_or_404(Questionnaire, link_code=link_code)
    id_respons = request.session.get('id_respons_terakhir')
    respons_terakhir = None

    if id_respons is not None:
        respons_terakhir = Response.objects.filter(
            id=id_respons,
            questionnaire=kuesioner,
        ).first()

    # Fallback cari respons milik pengguna/anonim jika session id tidak tersedia
    if respons_terakhir is None:
        if request.user.is_authenticated:
            respons_terakhir = Response.objects.filter(
                questionnaire=kuesioner,
                respondent=request.user,
            ).first()
        else:
            kunci_anonim = request.session.get(NAMA_SESSION_ANONIM, '')
            if kunci_anonim:
                respons_terakhir = Response.objects.filter(
                    questionnaire=kuesioner,
                    anonymous_key=kunci_anonim,
                ).first()

    jumlah_pertanyaan = kuesioner.questions.count()
    batas_waktu_minimum = jumlah_pertanyaan * kuesioner.seconds_per_question
    total_skor_pengguna = compute_score(request.user)

    context = {
        'kuesioner': kuesioner,
        'respons_terakhir': respons_terakhir,
        'batas_waktu_minimum': batas_waktu_minimum,
        'total_skor_pengguna': total_skor_pengguna,
    }
    return render(request, 'forms_app/selesai_pengisian.html', context)
