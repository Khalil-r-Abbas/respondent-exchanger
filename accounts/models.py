from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


username_validator = RegexValidator(
    regex=r'^[A-Za-z0-9_]{3,20}$',
    message='Username harus 3 sampai 20 karakter (huruf, angka, atau garis bawah).',
)


class User(AbstractUser):
    """Custom user model matching SRS Section 4.1 and Section 7."""

    username = models.CharField(
        max_length=20,
        unique=True,
        validators=[username_validator],
        help_text='3 sampai 20 karakter: huruf, angka, garis bawah.',
    )
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    registration_ip = models.GenericIPAddressField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'accounts_user'
        ordering = ['date_joined', 'id']
        indexes = [
            models.Index(fields=['registration_ip'], name='idx_user_reg_ip'),
            models.Index(fields=['date_joined'], name='idx_user_date_joined'),
        ]

    def __str__(self):
        return self.username
