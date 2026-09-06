from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        "report_type",
        "status",
        "progress",
        "created_by",
        "created_at",
    ]
    list_filter = [
        "report_type",
        "status",
    ]