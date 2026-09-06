from rest_framework import serializers

from .models import AbnormalEvent


class AbnormalEventSerializer(serializers.ModelSerializer):
    panel_full_code = serializers.CharField(source="panel.full_code", read_only=True)
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AbnormalEvent
        fields = (
            "id", "panel", "panel_full_code", "event_type", "event_type_display",
            "status", "status_display", "opened_at", "closed_at", "reason",
            "source_job", "closed_by", "closed_note", "created_at", "updated_at",
        )
        read_only_fields = ("opened_at", "closed_at", "created_at", "updated_at")