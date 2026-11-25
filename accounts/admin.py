from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'email',
        'email_verified',
        'is_blocked',
        'is_staff',
        'registration_ip',
        'date_joined',
    )
    list_filter = ('email_verified', 'is_blocked', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'registration_ip', 'last_ip')
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Status Verifikasi & Moderasi',
            {'fields': ('email_verified', 'is_blocked', 'registration_ip', 'last_ip')},
        ),
    )
