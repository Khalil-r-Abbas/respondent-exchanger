import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


def generate_link_code():
    """Generate an unguessable URL-safe code for public questionnaire links."""
    return secrets.token_urlsafe(9)


class Questionnaire(models.Model):
    """Questionnaire entity (Kuesioner) per SRS Section 4.2 and Section 7."""

    class Language(models.TextChoices):
        INDONESIAN = 'id', 'Indonesia'
        ENGLISH = 'en', 'Inggris'
        OTHER = 'other', 'Lainnya'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draf'
        PUBLISHED = 'published', 'Terbit'
        HIDDEN = 'hidden', 'Disembunyikan'
        REMOVED = 'removed', 'Dihapus Admin'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='questionnaires',
    )
    link_code = models.CharField(
        max_length=32,
        unique=True,
        default=generate_link_code,
        db_index=True,
    )
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True, default='')
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.INDONESIAN,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    allow_anonymous = models.BooleanField(default=True)
    show_respondent_username = models.BooleanField(default=False)
    seconds_per_question = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(10), MaxValueValidator(20)],
    )
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'forms_questionnaire'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['link_code'], name='idx_q_link_code'),
            models.Index(fields=['expires_at'], name='idx_q_expires_at'),
            models.Index(fields=['status', 'expires_at'], name='idx_q_status_expires'),
        ]

    @property
    def is_expired(self):
        return self.expires_at is not None and timezone.now() >= self.expires_at

    @property
    def is_open(self):
        return self.status == self.Status.PUBLISHED and not self.is_expired

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class Question(models.Model):
    """Question entity (Pertanyaan) belonging to a Questionnaire."""

    class QuestionType(models.TextChoices):
        SHORT_TEXT = 'short_text', 'Jawaban Singkat'
        LONG_TEXT = 'long_text', 'Jawaban Panjang'
        SINGLE_CHOICE = 'single_choice', 'Pilihan Ganda'
        MULTIPLE_CHOICE = 'multiple_choice', 'Kotak Centang'
        DROPDOWN = 'dropdown', 'Dropdown'
        RATING = 'rating', 'Rating'

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    order = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    text = models.CharField(max_length=300)
    is_required = models.BooleanField(default=True)
    options = models.JSONField(default=list, blank=True)
    rating_max = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
    )

    class Meta:
        db_table = 'forms_question'
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['questionnaire', 'order'],
                name='uq_question_order_per_questionnaire',
            ),
        ]

    def __str__(self):
        return f'#{self.order} {self.text[:40]}'


class SubmissionSession(models.Model):
    """Server-side filling session (Sesi pengisian) for minimum timer enforcement."""

    class SessionStatus(models.TextChoices):
        ACTIVE = 'active', 'Aktif'
        SUBMITTED = 'submitted', 'Terkirim'
        CANCELLED = 'cancelled', 'Dibatalkan'
        EXPIRED = 'expired', 'Berakhir'

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='submission_sessions',
    )
    anonymous_key = models.CharField(max_length=64, blank=True, default='', db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
    )

    class Meta:
        db_table = 'forms_submission_session'
        ordering = ['-started_at', '-id']
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_session_user_status'),
            models.Index(fields=['anonymous_key', 'status'], name='idx_session_anon_status'),
        ]

    def __str__(self):
        actor = self.user.username if self.user else f'anon:{self.anonymous_key[:8]}'
        return f'Session {self.id} ({actor}) - {self.status}'


class Response(models.Model):
    """Submitted response (Respons) with server-verified timing and point flags."""

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responses',
    )
    anonymous_key = models.CharField(max_length=64, blank=True, default='')
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField(default=timezone.now)
    duration_seconds = models.PositiveIntegerField()
    is_too_fast = models.BooleanField(default=False)
    is_counted = models.BooleanField(default=False)
    points_awarded = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'forms_response'
        ordering = ['-submitted_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['questionnaire', 'respondent'],
                condition=Q(respondent__isnull=False),
                name='uq_response_per_user_per_questionnaire',
            ),
            models.UniqueConstraint(
                fields=['questionnaire', 'anonymous_key'],
                condition=~Q(anonymous_key=''),
                name='uq_response_per_anon_per_questionnaire',
            ),
        ]
        indexes = [
            models.Index(fields=['submitted_at'], name='idx_resp_submitted_at'),
        ]

    def __str__(self):
        who = self.respondent.username if self.respondent else 'Anonim'
        return f'Response #{self.id} ({who}) -> Q#{self.questionnaire_id}'


class Answer(models.Model):
    """Individual answer (Jawaban) tied to a Response and Question."""

    response = models.ForeignKey(
        Response,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    value = models.JSONField(default=None, null=True, blank=True)

    class Meta:
        db_table = 'forms_answer'
        ordering = ['question__order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['response', 'question'],
                name='uq_answer_per_question_per_response',
            ),
        ]

    def __str__(self):
        return f'Answer R#{self.response_id} Q#{self.question_id}'


class Report(models.Model):
    """Moderation report (Laporan) filed by a verified user on a Questionnaire."""

    class Reason(models.TextChoices):
        ILLEGAL_CONTENT = 'illegal_content', 'Konten Ilegal'
        SENSITIVE_DATA = 'sensitive_data', 'Meminta Data Sensitif'
        SPAM = 'spam', 'Spam'
        ABUSIVE_CONTENT = 'abusive_content', 'Konten Kasar'
        OTHER = 'other', 'Lainnya'

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    reason = models.CharField(max_length=32, choices=Reason.choices)
    note = models.TextField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'forms_report'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['questionnaire', 'reporter'],
                name='uq_report_per_reporter_per_questionnaire',
            ),
        ]

    def __str__(self):
        return f'Report Q#{self.questionnaire_id} by {self.reporter.username}'
