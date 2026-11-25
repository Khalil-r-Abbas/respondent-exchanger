from django.conf import settings
from django.db import models
from django.utils import timezone


class PointLedger(models.Model):
    """Append-only point ledger (Buku besar poin) per SRS Section 4.4 and Section 7."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='point_entries',
    )
    # SET_NULL preserves earned points if the creator deletes the questionnaire.
    questionnaire = models.ForeignKey(
        'forms_app.Questionnaire',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='point_entries',
    )
    response = models.ForeignKey(
        'forms_app.Response',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='point_entries',
    )
    points = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'core_point_ledger'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(
                fields=['user', 'is_revoked', 'created_at'],
                name='idx_ledger_user_revoked_dt',
            ),
        ]

    def __str__(self):
        status = 'dicabut' if self.is_revoked else 'aktif'
        return f'{self.user.username}: +{self.points} ({status})'


class AdminAuditLog(models.Model):
    """Immutable audit log of admin moderation actions (Log audit admin)."""

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_audit_logs',
    )
    action = models.CharField(max_length=64)
    target_object = models.CharField(max_length=120)
    details = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'core_admin_audit_log'
        ordering = ['-created_at', '-id']

    def __str__(self):
        actor = self.admin.username if self.admin else 'system'
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {actor}: {self.action} ({self.target_object})'
