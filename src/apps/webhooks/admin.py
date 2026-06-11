from django.contrib import admin

from .models import WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_event_id", "event_type", "status", "attempts", "received_at")
    list_filter = ("provider", "status")
    search_fields = ("external_event_id", "event_type")
    readonly_fields = tuple(f.name for f in WebhookEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
