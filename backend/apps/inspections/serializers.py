from rest_framework import serializers

from apps.stations.models import Panel

from .models import InspectionEvent, InspectionRecord, InspectionTask, Waypoint


class WaypointSerializer(serializers.ModelSerializer):
    panel_full_code = serializers.CharField(source="panel.full_code", read_only=True)
    panel_short_code = serializers.CharField(source="panel.short_code", read_only=True)
    region_name = serializers.CharField(source="panel.array.region.name", read_only=True)
    array_code = serializers.CharField(source="panel.array.code", read_only=True)

    class Meta:
        model = Waypoint
        fields = [
            "id", "task_id", "panel_id", "panel_full_code", "panel_short_code",
            "region_name", "array_code", "row", "column", "order",
            "status", "visited_at", "uploaded_media_id", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at", "visited_at"]


class InspectionEventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InspectionEvent
        fields = ["id", "task_id", "event_type", "description", "created_by_name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ""
        profile = getattr(obj.created_by, "operator_profile", None)
        return profile.display_name if profile else obj.created_by.get_full_name() or obj.created_by.username


class InspectionTaskListSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source="station.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InspectionTask
        fields = [
            "id", "title", "station_id", "station_name", "status",
            "total_waypoints", "visited_waypoints", "coverage",
            "created_by_name", "confirmed_at", "started_at", "completed_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "total_waypoints", "visited_waypoints", "coverage",
            "created_by_name", "confirmed_at", "started_at", "completed_at",
            "created_at", "updated_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ""
        profile = getattr(obj.created_by, "operator_profile", None)
        return profile.display_name if profile else obj.created_by.get_full_name() or obj.created_by.username


class InspectionTaskDetailSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source="station.name", read_only=True)
    station_code = serializers.CharField(source="station.code", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    confirmed_by_name = serializers.SerializerMethodField()
    waypoints = WaypointSerializer(many=True, read_only=True)
    events = InspectionEventSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = InspectionTask
        fields = [
            "id", "title", "description", "station_id", "station_name", "station_code",
            "status", "total_waypoints", "visited_waypoints", "coverage",
            "progress", "waypoints", "events",
            "created_by_name", "confirmed_by_name",
            "confirmed_at", "started_at", "completed_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "total_waypoints", "visited_waypoints", "coverage",
            "progress", "waypoints", "events",
            "created_by_name", "confirmed_by_name",
            "confirmed_at", "started_at", "completed_at",
            "created_at", "updated_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ""
        profile = getattr(obj.created_by, "operator_profile", None)
        return profile.display_name if profile else obj.created_by.get_full_name() or obj.created_by.username

    def get_confirmed_by_name(self, obj):
        if not obj.confirmed_by:
            return ""
        profile = getattr(obj.confirmed_by, "operator_profile", None)
        return profile.display_name if profile else obj.confirmed_by.get_full_name() or obj.confirmed_by.username

    def get_progress(self, obj):
        if obj.total_waypoints == 0:
            return 0.0
        return round(obj.visited_waypoints / obj.total_waypoints * 100, 1)


class InspectionTaskCreateSerializer(serializers.ModelSerializer):
    from apps.stations.models import Station

    station_id = serializers.PrimaryKeyRelatedField(
        source="station", queryset=Station.objects.filter(is_active=True)
    )

    class Meta:
        model = InspectionTask
        fields = ["title", "description", "station_id"]


class InspectionRecordSerializer(serializers.ModelSerializer):
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    status_label = serializers.SerializerMethodField()
    task_title = serializers.CharField(source="task.title", read_only=True, default="")
    panel_full_code = serializers.CharField(source="panel.full_code", read_only=True, default="")
    region_name = serializers.CharField(source="panel.array.region.name", read_only=True, default="")
    array_code = serializers.CharField(source="panel.array.code", read_only=True, default="")
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = InspectionRecord
        fields = [
            "id", "source", "source_label", "status", "status_label", "summary", "details",
            "task_id", "task_title", "panel_id", "panel_full_code", "region_name", "array_code",
            "operator_name", "recorded_at",
        ]

    def get_status_label(self, obj):
        return dict(Panel.Status.choices).get(obj.status, obj.status or "未知")

    def get_operator_name(self, obj):
        if not obj.operator:
            return "系统"
        profile = getattr(obj.operator, "operator_profile", None)
        return profile.display_name if profile else obj.operator.get_full_name() or obj.operator.username
