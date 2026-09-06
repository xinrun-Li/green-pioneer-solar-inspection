from django.contrib import admin

from .models import AbnormalEvent


@admin.register(AbnormalEvent)
class AbnormalEventAdmin(admin.ModelAdmin):
    list_display = ("id", "panel", "event_type", "status", "opened_at", "closed_at", "source_job")
    list_filter = ("event_type", "status")
    search_fields = ("panel__full_code", "reason")