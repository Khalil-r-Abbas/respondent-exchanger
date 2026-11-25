from django.contrib import admin

from .models import AdminAuditLog, PointLedger


@admin.register(PointLedger)
class PointLedgerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'questionnaire', 'response', 'points', 'is_revoked', 'created_at')
    list_filter = ('is_revoked',)
    search_fields = ('user__username', 'questionnaire__title', 'revocation_reason')


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'admin', 'action', 'target_object', 'created_at')
    list_filter = ('action',)
    search_fields = ('admin__username', 'action', 'target_object', 'details')
