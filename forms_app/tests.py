from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import PointLedger
from forms_app.models import Answer, Question, Questionnaire, Report, Response, SubmissionSession


User = get_user_model()


class DatabaseModelRulesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='pemilik_1',
            email='pemilik1@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.respondent = User.objects.create_user(
            username='pengisi_1',
            email='pengisi1@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.other_user = User.objects.create_user(
            username='pengisi_2',
            email='pengisi2@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.questionnaire = Questionnaire.objects.create(
            owner=self.owner,
            title='Kuesioner Uji Relasi',
            description='Deskripsi uji',
            language=Questionnaire.Language.INDONESIAN,
            status=Questionnaire.Status.PUBLISHED,
            published_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=3),
        )
        self.question = Question.objects.create(
            questionnaire=self.questionnaire,
            order=1,
            question_type=Question.QuestionType.SHORT_TEXT,
            text='Bagaimana pendapat Anda?',
            is_required=True,
        )

    def test_delete_questionnaire_cascades_questions_and_preserves_point_ledger(self):
        now = timezone.now()
        resp = Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=self.respondent,
            started_at=now - timedelta(seconds=25),
            submitted_at=now,
            duration_seconds=25,
            is_too_fast=False,
            is_counted=True,
            points_awarded=1,
        )
        Answer.objects.create(response=resp, question=self.question, value='Bagus')
        ledger = PointLedger.objects.create(
            user=self.respondent,
            questionnaire=self.questionnaire,
            response=resp,
            points=1,
        )

        self.questionnaire.delete()

        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(Response.objects.count(), 0)
        self.assertEqual(Answer.objects.count(), 0)

        ledger.refresh_from_db()
        self.assertEqual(ledger.points, 1)
        self.assertIsNone(ledger.questionnaire)
        self.assertIsNone(ledger.response)

    def test_delete_account_anonymizes_responses_and_removes_owned_questionnaires(self):
        now = timezone.now()
        resp = Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=self.respondent,
            started_at=now - timedelta(seconds=30),
            submitted_at=now,
            duration_seconds=30,
            is_counted=True,
            points_awarded=1,
        )
        Answer.objects.create(response=resp, question=self.question, value='Mantap')
        PointLedger.objects.create(
            user=self.respondent,
            questionnaire=self.questionnaire,
            response=resp,
            points=1,
        )

        # Hapus akun pengisi: respons tetap ada dengan respondent=None (anonim)
        self.respondent.delete()

        resp.refresh_from_db()
        self.assertIsNone(resp.respondent)
        self.assertEqual(resp.answers.count(), 1)
        self.assertEqual(PointLedger.objects.count(), 0)

        # Hapus akun pemilik: kuesioner miliknya ikut terhapus
        self.owner.delete()
        self.assertEqual(Questionnaire.objects.count(), 0)

    def test_unique_one_report_per_reporter_per_questionnaire(self):
        Report.objects.create(
            questionnaire=self.questionnaire,
            reporter=self.respondent,
            reason=Report.Reason.SPAM,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Report.objects.create(
                    questionnaire=self.questionnaire,
                    reporter=self.respondent,
                    reason=Report.Reason.OTHER,
                )

    def test_unique_one_response_per_account_per_questionnaire_allows_multiple_anonymous(self):
        now = timezone.now()
        Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=self.respondent,
            started_at=now - timedelta(seconds=20),
            submitted_at=now,
            duration_seconds=20,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Response.objects.create(
                    questionnaire=self.questionnaire,
                    respondent=self.respondent,
                    started_at=now - timedelta(seconds=20),
                    submitted_at=now,
                    duration_seconds=20,
                )

        # Dua respons anonim dengan anonymous_key berbeda atau kosong tetap diizinkan
        Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=None,
            anonymous_key='browser-a',
            started_at=now - timedelta(seconds=20),
            submitted_at=now,
            duration_seconds=20,
        )
        Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=None,
            anonymous_key='browser-b',
            started_at=now - timedelta(seconds=20),
            submitted_at=now,
            duration_seconds=20,
        )
        Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=None,
            anonymous_key='',
            started_at=now - timedelta(seconds=20),
            submitted_at=now,
            duration_seconds=20,
        )
        Response.objects.create(
            questionnaire=self.questionnaire,
            respondent=None,
            anonymous_key='',
            started_at=now - timedelta(seconds=20),
            submitted_at=now,
            duration_seconds=20,
        )
        self.assertEqual(Response.objects.filter(questionnaire=self.questionnaire).count(), 5)

        # Anonymous key non-kosong yang sama pada kuesioner yang sama harus ditolak
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Response.objects.create(
                    questionnaire=self.questionnaire,
                    respondent=None,
                    anonymous_key='browser-a',
                    started_at=now - timedelta(seconds=20),
                    submitted_at=now,
                    duration_seconds=20,
                )

    def test_questionnaire_indexes_and_session_creation(self):
        index_fields = [tuple(idx.fields) for idx in Questionnaire._meta.indexes]
        self.assertIn(('link_code',), index_fields)
        self.assertIn(('expires_at',), index_fields)

        session = SubmissionSession.objects.create(
            questionnaire=self.questionnaire,
            user=self.other_user,
        )
        self.assertEqual(session.status, SubmissionSession.SessionStatus.ACTIVE)


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_is_idempotent_and_populates_expected_counts(self):
        call_command('seed_demo')
        call_command('seed_demo')

        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(Questionnaire.objects.count(), 8)
        self.assertGreaterEqual(Response.objects.count(), 6)
        self.assertGreaterEqual(PointLedger.objects.count(), 4)


class PengisianDanPoinTests(TestCase):
    def setUp(self):
        self.pemilik = User.objects.create_user(
            username='pemilik_uji',
            email='pemilik_uji@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.responden = User.objects.create_user(
            username='responden_uji',
            email='responden_uji@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.belum_verifikasi = User.objects.create_user(
            username='belum_verif',
            email='belum_verif@example.com',
            password='Password123!',
            email_verified=False,
        )
        self.kuesioner = Questionnaire.objects.create(
            owner=self.pemilik,
            link_code='uji_pengisian_01',
            title='Kuesioner Pengisian & Poin',
            description='Uji alur pengisian dan timer server',
            language=Questionnaire.Language.INDONESIAN,
            status=Questionnaire.Status.PUBLISHED,
            allow_anonymous=True,
            seconds_per_question=10,
            published_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=2),
        )
        self.q1 = Question.objects.create(
            questionnaire=self.kuesioner,
            order=1,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            text='Pilih satu opsi',
            is_required=True,
            options=['A', 'B'],
        )
        self.q2 = Question.objects.create(
            questionnaire=self.kuesioner,
            order=2,
            question_type=Question.QuestionType.RATING,
            text='Beri rating',
            is_required=True,
            rating_max=5,
        )

    def test_sesi_pengisian_dibuat_dan_dilanjutkan_dari_server(self):
        self.client.force_login(self.responden)
        url = f'/q/{self.kuesioner.link_code}/'

        res1 = self.client.get(url)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(SubmissionSession.objects.count(), 1)
        sesi_awal = SubmissionSession.objects.first()

        # Membuka ulang halaman harus melanjutkan sesi yang sama, bukan membuat baru
        res2 = self.client.get(url)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(SubmissionSession.objects.count(), 1)
        self.assertEqual(res2.context['sesi_pengisian'].id, sesi_awal.id)
        self.assertEqual(res2.context['batas_waktu_minimum'], 20)

    def test_kirim_terlalu_cepat_tetap_simpan_tanpa_poin(self):
        from core.points import compute_score

        self.client.force_login(self.responden)
        url = f'/q/{self.kuesioner.link_code}/'

        self.client.get(url)
        res_post = self.client.post(
            url,
            {
                f'pertanyaan_{self.q1.id}': 'A',
                f'pertanyaan_{self.q2.id}': '4',
            },
        )
        self.assertRedirects(res_post, f'/q/{self.kuesioner.link_code}/selesai/')

        respons = Response.objects.get(questionnaire=self.kuesioner, respondent=self.responden)
        self.assertTrue(respons.is_too_fast)
        self.assertFalse(respons.is_counted)
        self.assertEqual(respons.points_awarded, 0)
        self.assertEqual(Answer.objects.filter(response=respons).count(), 2)
        self.assertEqual(PointLedger.objects.count(), 0)
        self.assertEqual(compute_score(self.responden), 0)

    def test_kirim_sesuai_waktu_mendapat_poin_dan_update_compute_score(self):
        from core.points import compute_score

        self.client.force_login(self.responden)
        url = f'/q/{self.kuesioner.link_code}/'
        self.client.get(url)

        # Simulasikan waktu mulai di server sudah melewati batas minimum (20 detik)
        sesi = SubmissionSession.objects.get(questionnaire=self.kuesioner, user=self.responden)
        sesi.started_at = timezone.now() - timedelta(seconds=25)
        sesi.save(update_fields=['started_at'])

        res_post = self.client.post(
            url,
            {
                f'pertanyaan_{self.q1.id}': 'B',
                f'pertanyaan_{self.q2.id}': '5',
            },
        )
        self.assertRedirects(res_post, f'/q/{self.kuesioner.link_code}/selesai/')

        respons = Response.objects.get(questionnaire=self.kuesioner, respondent=self.responden)
        self.assertFalse(respons.is_too_fast)
        self.assertTrue(respons.is_counted)
        self.assertEqual(respons.points_awarded, 2)
        self.assertEqual(PointLedger.objects.filter(user=self.responden).count(), 1)
        self.assertEqual(compute_score(self.responden), 2)

        sesi.refresh_from_db()
        self.assertEqual(sesi.status, SubmissionSession.SessionStatus.SUBMITTED)

        # Pengisian ulang oleh pengguna yang sama harus ditolak
        res_ulang = self.client.get(url)
        self.assertEqual(res_ulang.context['status_akses'], 'sudah_mengisi')

    def test_pemilik_dan_belum_verifikasi_tidak_mendapat_poin(self):
        from core.points import compute_score

        for pengguna in (self.pemilik, self.belum_verifikasi):
            self.client.force_login(pengguna)
            url = f'/q/{self.kuesioner.link_code}/'
            self.client.get(url)
            sesi = SubmissionSession.objects.get(questionnaire=self.kuesioner, user=pengguna)
            sesi.started_at = timezone.now() - timedelta(seconds=30)
            sesi.save(update_fields=['started_at'])

            self.client.post(
                url,
                {
                    f'pertanyaan_{self.q1.id}': 'A',
                    f'pertanyaan_{self.q2.id}': '3',
                },
            )
            self.assertEqual(compute_score(pengguna), 0)

        self.assertEqual(PointLedger.objects.count(), 0)

    def test_pengisian_anonim_tersimpan_tanpa_poin_dan_compute_score_abaikan_revoked(self):
        from core.points import compute_score

        url = f'/q/{self.kuesioner.link_code}/'
        self.client.get(url)
        sesi = SubmissionSession.objects.get(questionnaire=self.kuesioner, user__isnull=True)
        sesi.started_at = timezone.now() - timedelta(seconds=30)
        sesi.save(update_fields=['started_at'])

        self.client.post(
            url,
            {
                f'pertanyaan_{self.q1.id}': 'A',
                f'pertanyaan_{self.q2.id}': '5',
            },
        )
        respons_anonim = Response.objects.get(questionnaire=self.kuesioner, respondent__isnull=True)
        self.assertFalse(respons_anonim.is_too_fast)
        self.assertFalse(respons_anonim.is_counted)
        self.assertEqual(respons_anonim.points_awarded, 0)

        # Uji compute_score mengabaikan entri poin yang dicabut
        PointLedger.objects.create(user=self.responden, points=3, is_revoked=False)
        PointLedger.objects.create(user=self.responden, points=5, is_revoked=True)
        self.assertEqual(compute_score(self.responden), 3)
