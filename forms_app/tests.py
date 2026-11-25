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
