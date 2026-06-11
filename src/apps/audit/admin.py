from django.contrib import admin

from .models import TransactionLog


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "target_type", "target_id", "actor_id", "timestamp")
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "actor_id", "action")
    readonly_fields = tuple(f.name for f in TransactionLog._meta.fields)
    ordering = ("-id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
