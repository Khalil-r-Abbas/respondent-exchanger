import json
import uuid
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.points import (
    catat_poin_ke_buku_besar,
    compute_score,
    tentukan_kelayakan_poin,
)

from .forms import QuestionnaireBuilderForm, PublishQuestionnaireForm
from .models import Answer, Question, Questionnaire, Response, SubmissionSession


MAX_DRAFTS = 6
MAX_ACTIVE_QUESTIONNAIRES = 3
DEV_BUILDER_USERNAME = 'demo_builder'


def dev_login_required(view_func):
    """Use a local dummy account only when explicitly enabled in development."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated and getattr(settings, 'DEV_AUTO_LOGIN', False):
            user_model = get_user_model()
            user, _created = user_model.objects.get_or_create(
                username=DEV_BUILDER_USERNAME,
                defaults={
                    'email': 'demo_builder@example.com',
                    'email_verified': True,
                },
            )
            fields_to_update = []
            if not user.has_usable_password():
                user.set_password('DemoPass123!')
                fields_to_update.append('password')
            if not user.email_verified:
                user.email_verified = True
                fields_to_update.append('email_verified')
            if fields_to_update:
                user.save(update_fields=fields_to_update)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return login_required(view_func)(request, *args, **kwargs)

    return wrapped


def _question_payload(questionnaire):
    return [
        {
            'question_type': question.question_type,
            'text': question.text,
            'is_required': question.is_required,
            'options': question.options or [],
            'rating_max': question.rating_max,
        }
        for question in questionnaire.questions.all()
    ]


def _save_questions(questionnaire, payload):
    questionnaire.questions.all().delete()
    Question.objects.bulk_create([
        Question(
            questionnaire=questionnaire,
            order=order,
            question_type=item['question_type'],
            text=item['text'],
            is_required=item['is_required'],
            options=item['options'],
            rating_max=item['rating_max'],
        )
        for order, item in enumerate(payload, start=1)
    ])


def _owned_questionnaire(request, pk):
    return get_object_or_404(
        Questionnaire.objects.prefetch_related('questions'),
        pk=pk,
        owner=request.user,
    )


@dev_login_required
def questionnaire_list(request):
    questionnaires = list(
        Questionnaire.objects.filter(owner=request.user)
        .annotate(response_count=Count('responses'))
        .prefetch_related('questions')
    )
    drafts = [item for item in questionnaires if item.status == Questionnaire.Status.DRAFT]
    published = [
        item for item in questionnaires
        if item.status == Questionnaire.Status.PUBLISHED and not item.is_expired
    ]
    ended = [
        item for item in questionnaires
        if item.status != Questionnaire.Status.DRAFT and (item.is_expired or item.status != Questionnaire.Status.PUBLISHED)
    ]
    return render(request, 'forms_app/questionnaire_list.html', {
        'drafts': drafts,
        'published': published,
        'ended': ended,
        'draft_limit': MAX_DRAFTS,
        'active_limit': MAX_ACTIVE_QUESTIONNAIRES,
    })


@dev_login_required
def questionnaire_builder(request, pk=None):
    questionnaire = _owned_questionnaire(request, pk) if pk else None
    if questionnaire and questionnaire.status != Questionnaire.Status.DRAFT:
        messages.error(request, 'Kuesioner yang sudah terbit tidak dapat diubah.')
        return redirect('forms_app:questionnaire_preview', pk=questionnaire.pk)

    if questionnaire is None and request.method == 'GET':
        if Questionnaire.objects.filter(owner=request.user, status=Questionnaire.Status.DRAFT).count() >= MAX_DRAFTS:
            messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
            return redirect('forms_app:questionnaire_list')

    if request.method == 'POST':
        if questionnaire is None and Questionnaire.objects.filter(
            owner=request.user,
            status=Questionnaire.Status.DRAFT,
        ).count() >= MAX_DRAFTS:
            messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
            return redirect('forms_app:questionnaire_list')

        form = QuestionnaireBuilderForm(request.POST, instance=questionnaire)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if questionnaire is None:
                    saved.owner = request.user
                saved.status = Questionnaire.Status.DRAFT
                saved.save()
                _save_questions(saved, form.questions_payload)
            messages.success(request, 'Draf kuesioner berhasil disimpan.')
            if request.POST.get('save_and_preview'):
                return redirect('forms_app:questionnaire_preview', pk=saved.pk)
            return redirect('forms_app:questionnaire_edit', pk=saved.pk)
    else:
        initial = {}
        if questionnaire:
            initial['questions_json'] = json.dumps(_question_payload(questionnaire), ensure_ascii=False)
        else:
            initial['questions_json'] = '[]'
        form = QuestionnaireBuilderForm(instance=questionnaire, initial=initial)

    return render(request, 'forms_app/questionnaire_builder.html', {
        'form': form,
        'questionnaire': questionnaire,
        'initial_questions_json': form['questions_json'].value() or '[]',
        'max_questions': 20,
    })


@dev_login_required
def questionnaire_preview(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    return render(request, 'forms_app/questionnaire_preview.html', {
        'questionnaire': questionnaire,
        'preview': True,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })


@dev_login_required
def questionnaire_publish(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    if questionnaire.status != Questionnaire.Status.DRAFT:
        messages.error(request, 'Hanya draf yang dapat diterbitkan.')
        return redirect('forms_app:questionnaire_preview', pk=pk)

    form = PublishQuestionnaireForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if not getattr(request.user, 'email_verified', False):
            form.add_error(None, 'Email harus terverifikasi sebelum menerbitkan kuesioner.')
        elif not questionnaire.questions.exists():
            form.add_error(None, 'Tambahkan minimal satu pertanyaan sebelum menerbitkan.')
        elif Questionnaire.objects.filter(
            owner=request.user,
            status=Questionnaire.Status.PUBLISHED,
            expires_at__gt=timezone.now(),
        ).exclude(pk=pk).count() >= MAX_ACTIVE_QUESTIONNAIRES:
            form.add_error(None, f'Batas {MAX_ACTIVE_QUESTIONNAIRES} kuesioner aktif tercapai.')
        else:
            now = timezone.now()
            questionnaire.status = Questionnaire.Status.PUBLISHED
            questionnaire.published_at = now
            questionnaire.expires_at = now + timedelta(days=form.cleaned_data['duration_days'])
            questionnaire.save(update_fields=['status', 'published_at', 'expires_at'])
            messages.success(request, 'Kuesioner berhasil diterbitkan dan sekarang terkunci.')
            return redirect('forms_app:questionnaire_preview', pk=pk)

    return render(request, 'forms_app/questionnaire_publish.html', {
        'questionnaire': questionnaire,
        'form': form,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })


@dev_login_required
@require_POST
def questionnaire_duplicate(request, pk):
    original = _owned_questionnaire(request, pk)
    if Questionnaire.objects.filter(owner=request.user, status=Questionnaire.Status.DRAFT).count() >= MAX_DRAFTS:
        messages.error(request, f'Batas draf tercapai. Maksimal {MAX_DRAFTS} draf per pengguna.')
        return redirect('forms_app:questionnaire_list')

    with transaction.atomic():
        duplicate = Questionnaire.objects.create(
            owner=request.user,
            title=f'Salinan: {original.title}'[:120],
            description=original.description,
            language=original.language,
            status=Questionnaire.Status.DRAFT,
            allow_anonymous=original.allow_anonymous,
            show_respondent_username=original.show_respondent_username,
            seconds_per_question=original.seconds_per_question,
        )
        _save_questions(duplicate, _question_payload(original))
    messages.success(request, 'Kuesioner berhasil diduplikasi sebagai draf.')
    return redirect('forms_app:questionnaire_edit', pk=duplicate.pk)


@dev_login_required
@require_POST
def questionnaire_delete(request, pk):
    questionnaire = _owned_questionnaire(request, pk)
    questionnaire.delete()
    messages.success(request, 'Kuesioner dan responsnya berhasil dihapus.')
    return redirect('forms_app:questionnaire_list')


def public_questionnaire(request, link_code):
    questionnaire = get_object_or_404(
        Questionnaire.objects.prefetch_related('questions'),
        link_code=link_code,
    )
    if not questionnaire.is_open:
        return render(request, 'forms_app/questionnaire_closed.html', {'questionnaire': questionnaire})
    return render(request, 'forms_app/questionnaire_preview.html', {
        'questionnaire': questionnaire,
        'preview': False,
        'minimum_seconds': questionnaire.questions.count() * questionnaire.seconds_per_question,
    })
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
            return redirect('forms_app:selesai_pengisian', link_code=kuesioner.link_code)

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
