import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Question, Questionnaire


class QuestionnaireBuilderFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='builder_owner',
            email='builder@example.com',
            password='Password123!',
            email_verified=True,
        )
        self.client.force_login(self.owner)

    def builder_payload(self, **overrides):
        payload = {
            'title': 'Survei Kebiasaan Belajar',
            'description': 'Pertanyaan singkat untuk penelitian kelas.',
            'language': Questionnaire.Language.INDONESIAN,
            'seconds_per_question': '10',
            'allow_anonymous': 'on',
            'questions_json': json.dumps([
                {
                    'question_type': Question.QuestionType.SINGLE_CHOICE,
                    'text': 'Seberapa sering kamu belajar?',
                    'is_required': True,
                    'options': ['Setiap hari', 'Beberapa kali seminggu'],
                    'rating_max': 5,
                },
                {
                    'question_type': Question.QuestionType.LONG_TEXT,
                    'text': 'Apa tantangan terbesarmu?',
                    'is_required': False,
                    'options': [],
                    'rating_max': 5,
                },
            ]),
        }
        payload.update(overrides)
        return payload

    def test_create_draft_saves_metadata_and_questions(self):
        response = self.client.post(reverse('forms_app:questionnaire_new'), self.builder_payload())

        self.assertRedirects(response, reverse('forms_app:questionnaire_edit', kwargs={'pk': 1}))
        questionnaire = Questionnaire.objects.get(owner=self.owner)
        self.assertEqual(questionnaire.status, Questionnaire.Status.DRAFT)
        self.assertEqual(questionnaire.questions.count(), 2)
        self.assertEqual(questionnaire.questions.first().options, ['Setiap hari', 'Beberapa kali seminggu'])

    def test_server_rejects_more_than_ten_options(self):
        questions = json.loads(self.builder_payload()['questions_json'])
        questions[0]['options'] = [f'Opsi {index}' for index in range(11)]
        response = self.client.post(
            reverse('forms_app:questionnaire_new'),
            self.builder_payload(questions_json=json.dumps(questions)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Questionnaire.objects.exists())
        self.assertContains(response, 'Maksimal 10 opsi')

    def test_publish_sets_expiry_and_public_page_is_read_only(self):
        self.client.post(reverse('forms_app:questionnaire_new'), self.builder_payload())
        questionnaire = Questionnaire.objects.get(owner=self.owner)

        response = self.client.post(
            reverse('forms_app:questionnaire_publish', kwargs={'pk': questionnaire.pk}),
            {'duration_days': '3', 'content_ack': 'on', 'lock_ack': 'on'},
        )

        questionnaire.refresh_from_db()
        self.assertRedirects(response, reverse('forms_app:questionnaire_preview', kwargs={'pk': questionnaire.pk}))
        self.assertEqual(questionnaire.status, Questionnaire.Status.PUBLISHED)
        self.assertGreater(questionnaire.expires_at, timezone.now() + timedelta(days=2))

        public_response = self.client.get(
            reverse('forms_app:public_questionnaire', kwargs={'link_code': questionnaire.link_code})
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, questionnaire.title)
        self.assertNotContains(public_response, 'Terbitkan kuesioner')

    def test_published_questionnaire_cannot_be_edited(self):
        questionnaire = Questionnaire.objects.create(
            owner=self.owner,
            title='Sudah Terbit',
            status=Questionnaire.Status.PUBLISHED,
            published_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=2),
        )
        Question.objects.create(
            questionnaire=questionnaire,
            order=1,
            question_type=Question.QuestionType.SHORT_TEXT,
            text='Pertanyaan lama',
        )

        response = self.client.post(
            reverse('forms_app:questionnaire_edit', kwargs={'pk': questionnaire.pk}),
            self.builder_payload(title='Percobaan ubah'),
        )

        self.assertRedirects(response, reverse('forms_app:questionnaire_preview', kwargs={'pk': questionnaire.pk}))
        questionnaire.refresh_from_db()
        self.assertEqual(questionnaire.title, 'Sudah Terbit')
        self.assertEqual(questionnaire.questions.first().text, 'Pertanyaan lama')

    def test_duplicate_creates_new_draft_with_questions(self):
        original = Questionnaire.objects.create(
            owner=self.owner,
            title='Survei Asli',
            status=Questionnaire.Status.PUBLISHED,
        )
        Question.objects.create(
            questionnaire=original,
            order=1,
            question_type=Question.QuestionType.RATING,
            text='Beri rating',
            rating_max=10,
        )

        response = self.client.post(reverse('forms_app:questionnaire_duplicate', kwargs={'pk': original.pk}))

        duplicate = Questionnaire.objects.exclude(pk=original.pk).get(owner=self.owner)
        self.assertRedirects(response, reverse('forms_app:questionnaire_edit', kwargs={'pk': duplicate.pk}))
        self.assertEqual(duplicate.status, Questionnaire.Status.DRAFT)
        self.assertEqual(duplicate.title, 'Salinan: Survei Asli')
        self.assertEqual(duplicate.questions.count(), 1)

    def test_sixth_draft_is_allowed_but_seventh_is_rejected(self):
        for index in range(6):
            Questionnaire.objects.create(owner=self.owner, title=f'Draf {index + 1}')

        response = self.client.get(reverse('forms_app:questionnaire_new'))

        self.assertRedirects(response, reverse('forms_app:questionnaire_list'))
        self.assertEqual(Questionnaire.objects.filter(owner=self.owner).count(), 6)
