from rest_framework import serializers

from .models import Report
from apps.inspections.models import InspectionTask


class ReportListSerializer(serializers.ModelSerializer):
    created_by_username = serializers.SerializerMethodField()
    inspection_task_id = serializers.SerializerMethodField()
    inspection_task_title = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "report_type",
            "status",
            "progress",
            "created_at",
            "created_by_username",
            "inspection_task_id",
            "inspection_task_title",
        ]

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_inspection_task_id(self, obj):
        return obj.parameters.get("inspection_task_id")

    def get_inspection_task_title(self, obj):
        return obj.parameters.get("inspection_task_title", "")


class ReportDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.SerializerMethodField()
    inspection_task_id = serializers.SerializerMethodField()
    inspection_task_title = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "report_type",
            "status",
            "parameters",
            "filters",
            "snapshot_data",
            "file",
            "error_message",
            "progress",
            "created_by_username",
            "inspection_task_id",
            "inspection_task_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "file",
            "error_message",
            "progress",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_inspection_task_id(self, obj):
        return obj.parameters.get("inspection_task_id")

    def get_inspection_task_title(self, obj):
        return obj.parameters.get("inspection_task_title", "")


class ReportCreateSerializer(serializers.ModelSerializer):
    inspection_task_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Report
        fields = [
            "report_type",
            "parameters",
            "filters",
            "inspection_task_id",
        ]

    def validate_report_type(self, value):
        valid_types = [choice[0] for choice in Report.ReportType.choices]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"不支持的报告类型: {value}，可选值: {', '.join(valid_types)}"
            )
        return value

    def validate_inspection_task_id(self, value):
        task = InspectionTask.objects.select_related("station").filter(id=value).first()
        if task is None:
            raise serializers.ValidationError("巡检任务不存在")
        if task.status != InspectionTask.Status.COMPLETED:
            raise serializers.ValidationError("只有已完成的巡检任务才能生成分析报告")
        request = self.context.get("request")
        if request and not request.user.is_superuser:
            station_id = getattr(getattr(request.user, "operator_profile", None), "station_id", None)
            if station_id != task.station_id:
                raise serializers.ValidationError("无权访问该巡检任务")
        return value
