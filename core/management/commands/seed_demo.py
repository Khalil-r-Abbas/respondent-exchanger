from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import AdminAuditLog, PointLedger
from forms_app.models import Answer, Question, Questionnaire, Report, Response, SubmissionSession


class Command(BaseCommand):
    help = 'Mengisi data contoh (5 pengguna, 8 kuesioner, respons, dan poin) untuk pengembangan.'

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        now = timezone.now()

        users_spec = [
            ('andi_sutanto', 'andi@example.com', '192.168.1.10'),
            ('budi_pratama', 'budi@example.com', '192.168.1.11'),
            ('citra_lestari', 'citra@example.com', '192.168.1.12'),
            ('dewi_anggraini', 'dewi@example.com', '192.168.1.13'),
            ('eko_wijaya', 'eko@example.com', '192.168.1.14'),
        ]

        users = {}
        for idx, (username, email, ip_addr) in enumerate(users_spec):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'email_verified': True,
                    'registration_ip': ip_addr,
                    'last_ip': ip_addr,
                    'date_joined': now - timedelta(days=20 - idx * 3),
                },
            )
            if created:
                user.set_password('DemoPass123!')
                user.save(update_fields=['password'])
            users[username] = user

        questionnaires_spec = [
            {
                'link_code': 'demo_q_skripsi_ux',
                'owner': users['andi_sutanto'],
                'title': 'Evaluasi Usability Aplikasi Kampus',
                'description': 'Survei singkat untuk mahasiswa mengenai pengalaman memakai portal akademik.',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': True,
                'show_respondent_username': False,
                'seconds_per_question': 12,
                'published_at': now - timedelta(days=2),
                'expires_at': now + timedelta(days=5),
                'questions': [
                    (1, Question.QuestionType.SINGLE_CHOICE, 'Seberapa sering Anda mengakses portal akademik?', True, ['Setiap hari', 'Mingguan', 'Jarang'], 5),
                    (2, Question.QuestionType.RATING, 'Beri nilai kemudahan navigasi portal (1-5).', True, [], 5),
                    (3, Question.QuestionType.SHORT_TEXT, 'Fitur apa yang paling sering Anda gunakan?', True, [], 5),
                ],
            },
            {
                'link_code': 'demo_q_kopi_umkm',
                'owner': users['andi_sutanto'],
                'title': 'Preferensi Pembelian Kopi Susu Lokal',
                'description': 'Riset pasar UMKM kedai kopi untuk mahasiswa dan pekerja.',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': True,
                'show_respondent_username': True,
                'seconds_per_question': 10,
                'published_at': now - timedelta(days=1),
                'expires_at': now + timedelta(days=6),
                'questions': [
                    (1, Question.QuestionType.DROPDOWN, 'Rentang harga kopi yang paling sesuai?', True, ['< Rp15.000', 'Rp15.000 - Rp25.000', '> Rp25.000'], 5),
                    (2, Question.QuestionType.MULTIPLE_CHOICE, 'Faktor utama memilih kedai kopi?', True, ['Rasa', 'Harga', 'Wi-Fi', 'Lokasi'], 5),
                    (3, Question.QuestionType.LONG_TEXT, 'Saran menu atau promosi yang Anda harapkan.', False, [], 5),
                ],
            },
            {
                'link_code': 'demo_q_remote_work',
                'owner': users['budi_pratama'],
                'title': 'Remote Work Productivity Habits Survey',
                'description': 'Short academic study on focus tools and async communication.',
                'language': Questionnaire.Language.ENGLISH,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': False,
                'show_respondent_username': True,
                'seconds_per_question': 15,
                'published_at': now - timedelta(days=3),
                'expires_at': now + timedelta(days=4),
                'questions': [
                    (1, Question.QuestionType.SINGLE_CHOICE, 'Primary work setup?', True, ['Full remote', 'Hybrid', 'On-site'], 5),
                    (2, Question.QuestionType.RATING, 'Rate your focus level at home (1-10).', True, [], 10),
                ],
            },
            {
                'link_code': 'demo_q_belajar_ai',
                'owner': users['budi_pratama'],
                'title': 'Pemanfaatan AI dalam Tugas Kuliah',
                'description': 'Kuesioner penelitian etika dan efektivitas alat bantu AI.',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': True,
                'show_respondent_username': False,
                'seconds_per_question': 10,
                'published_at': now - timedelta(hours=12),
                'expires_at': now + timedelta(days=3),
                'questions': [
                    (1, Question.QuestionType.MULTIPLE_CHOICE, 'Keperluan memakai AI?', True, ['Ringkas materi', 'Debugging', 'Ide awal', 'Tata bahasa'], 5),
                    (2, Question.QuestionType.SHORT_TEXT, 'Sebutkan alat AI yang paling membantu.', True, [], 5),
                ],
            },
            {
                'link_code': 'demo_q_transportasi',
                'owner': users['citra_lestari'],
                'title': 'Kepuasan Transportasi Umum Perkotaan',
                'description': 'Mengukur ketepatan waktu dan kenyamanan rute bus kota.',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': True,
                'show_respondent_username': False,
                'seconds_per_question': 10,
                'published_at': now - timedelta(days=4),
                'expires_at': now + timedelta(days=2),
                'questions': [
                    (1, Question.QuestionType.RATING, 'Penilaian kebersihan armada (1-5).', True, [], 5),
                    (2, Question.QuestionType.SHORT_TEXT, 'Rute yang paling butuh penambahan unit?', True, [], 5),
                ],
            },
            {
                'link_code': 'demo_q_expired_old',
                'owner': users['dewi_anggraini'],
                'title': 'Evaluasi Event Seminar Teknologi 2026',
                'description': 'Kuesioner umpan balik peserta (sudah kedaluwarsa).',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.PUBLISHED,
                'allow_anonymous': True,
                'show_respondent_username': False,
                'seconds_per_question': 10,
                'published_at': now - timedelta(days=10),
                'expires_at': now - timedelta(days=3),
                'questions': [
                    (1, Question.QuestionType.RATING, 'Kepuasan keseluruhan acara.', True, [], 5),
                ],
            },
            {
                'link_code': 'demo_q_draft_baru',
                'owner': users['dewi_anggraini'],
                'title': 'Draf Survei Kebiasaan Olahraga Mahasiswa',
                'description': 'Masih berupa draf sebelum diterbitkan.',
                'language': Questionnaire.Language.INDONESIAN,
                'status': Questionnaire.Status.DRAFT,
                'allow_anonymous': True,
                'show_respondent_username': False,
                'seconds_per_question': 12,
                'published_at': None,
                'expires_at': None,
                'questions': [
                    (1, Question.QuestionType.SINGLE_CHOICE, 'Berapa kali olahraga per minggu?', True, ['0 kali', '1-2 kali', '3+ kali'], 5),
                ],
            },
            {
                'link_code': 'demo_q_hidden_mod',
                'owner': users['eko_wijaya'],
                'title': 'Survei Promosi Tautan Berulang',
                'description': 'Contoh kuesioner yang disembunyikan setelah laporan.',
                'language': Questionnaire.Language.OTHER,
                'status': Questionnaire.Status.HIDDEN,
                'allow_anonymous': False,
                'show_respondent_username': False,
                'seconds_per_question': 10,
                'published_at': now - timedelta(days=2),
                'expires_at': now + timedelta(days=5),
                'questions': [
                    (1, Question.QuestionType.SHORT_TEXT, 'Masukkan pendapat singkat Anda.', True, [], 5),
                ],
            },
        ]

        questionnaires = {}
        for spec in questionnaires_spec:
            q_obj, _ = Questionnaire.objects.get_or_create(
                link_code=spec['link_code'],
                defaults={
                    'owner': spec['owner'],
                    'title': spec['title'],
                    'description': spec['description'],
                    'language': spec['language'],
                    'status': spec['status'],
                    'allow_anonymous': spec['allow_anonymous'],
                    'show_respondent_username': spec['show_respondent_username'],
                    'seconds_per_question': spec['seconds_per_question'],
                    'published_at': spec['published_at'],
                    'expires_at': spec['expires_at'],
                },
            )
            for order, q_type, text, is_req, opts, rating_max in spec['questions']:
                Question.objects.get_or_create(
                    questionnaire=q_obj,
                    order=order,
                    defaults={
                        'question_type': q_type,
                        'text': text,
                        'is_required': is_req,
                        'options': opts,
                        'rating_max': rating_max,
                    },
                )
            questionnaires[spec['link_code']] = q_obj

        # Contoh respons & buku besar poin (valid, terlalu cepat, dan anonim)
        sample_submissions = [
            (
                'demo_q_skripsi_ux',
                users['budi_pratama'],
                '',
                48,
                False,
                True,
                3,
                now - timedelta(days=1),
                {1: 'Setiap hari', 2: 4, 3: 'Jadwal kuliah dan KRS'},
            ),
            (
                'demo_q_skripsi_ux',
                users['citra_lestari'],
                '',
                15,
                True,
                False,
                0,
                now - timedelta(hours=18),
                {1: 'Mingguan', 2: 3, 3: 'Nilai ujian'},
            ),
            (
                'demo_q_skripsi_ux',
                None,
                'anon-cookie-demo-001',
                42,
                False,
                False,
                0,
                now - timedelta(hours=8),
                {1: 'Setiap hari', 2: 5, 3: 'Unduh transkrip'},
            ),
            (
                'demo_q_kopi_umkm',
                users['citra_lestari'],
                '',
                35,
                False,
                True,
                2,
                now - timedelta(hours=10),
                {1: 'Rp15.000 - Rp25.000', 2: ['Rasa', 'Wi-Fi'], 3: 'Tambah varian matcha'},
            ),
            (
                'demo_q_remote_work',
                users['andi_sutanto'],
                '',
                40,
                False,
                True,
                2,
                now - timedelta(days=2),
                {1: 'Hybrid', 2: 8},
            ),
            (
                'demo_q_transportasi',
                users['andi_sutanto'],
                '',
                28,
                False,
                True,
                2,
                now - timedelta(days=3),
                {1: 4, 2: 'Koridor Stasiun - Kampus'},
            ),
        ]

        for link_code, respondent, anon_key, dur, too_fast, counted, pts, submitted_at, ans_map in sample_submissions:
            q_obj = questionnaires[link_code]
            started_at = submitted_at - timedelta(seconds=dur)

            if respondent is not None:
                resp, created = Response.objects.get_or_create(
                    questionnaire=q_obj,
                    respondent=respondent,
                    defaults={
                        'started_at': started_at,
                        'submitted_at': submitted_at,
                        'duration_seconds': dur,
                        'is_too_fast': too_fast,
                        'is_counted': counted,
                        'points_awarded': pts,
                    },
                )
            else:
                resp, created = Response.objects.get_or_create(
                    questionnaire=q_obj,
                    anonymous_key=anon_key,
                    defaults={
                        'respondent': None,
                        'started_at': started_at,
                        'submitted_at': submitted_at,
                        'duration_seconds': dur,
                        'is_too_fast': too_fast,
                        'is_counted': counted,
                        'points_awarded': pts,
                    },
                )

            if created:
                SubmissionSession.objects.create(
                    questionnaire=q_obj,
                    user=respondent,
                    anonymous_key=anon_key,
                    started_at=started_at,
                    last_activity_at=submitted_at,
                    status=SubmissionSession.SessionStatus.SUBMITTED,
                )
                for q_item in q_obj.questions.all():
                    if q_item.order in ans_map:
                        Answer.objects.create(
                            response=resp,
                            question=q_item,
                            value=ans_map[q_item.order],
                        )
                if counted and respondent is not None and pts > 0:
                    PointLedger.objects.create(
                        user=respondent,
                        questionnaire=q_obj,
                        response=resp,
                        points=pts,
                        created_at=submitted_at,
                    )

        # Contoh laporan dan log audit
        Report.objects.get_or_create(
            questionnaire=questionnaires['demo_q_hidden_mod'],
            reporter=users['andi_sutanto'],
            defaults={
                'reason': Report.Reason.SPAM,
                'note': 'Terindikasi tautan spam berulang.',
            },
        )
        if not AdminAuditLog.objects.filter(target_object='Questionnaire:demo_q_hidden_mod').exists():
            AdminAuditLog.objects.create(
                admin=None,
                action='auto_hide_questionnaire',
                target_object='Questionnaire:demo_q_hidden_mod',
                details='Contoh log audit penyembunyian kuesioner.',
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'seed_demo selesai: {User.objects.count()} pengguna, '
                f'{Questionnaire.objects.count()} kuesioner, '
                f'{Response.objects.count()} respons, '
                f'{PointLedger.objects.count()} entri buku besar poin.'
            )
        )
