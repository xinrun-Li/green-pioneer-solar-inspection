from django.contrib import admin

from .models import InspectionEvent, InspectionTask, Waypoint


@admin.register(InspectionTask)
class InspectionTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "station", "status", "total_waypoints", "visited_waypoints", "coverage", "created_by", "created_at")
    list_filter = ("status", "station")
    search_fields = ("title",)
    readonly_fields = ("total_waypoints", "visited_waypoints", "coverage", "created_at", "updated_at")


@admin.register(Waypoint)
class WaypointAdmin(admin.ModelAdmin):
    list_display = ("task", "panel", "order", "status", "visited_at")
    list_filter = ("status", "task")
    search_fields = ("task__title", "panel__full_code")


@admin.register(InspectionEvent)
class InspectionEventAdmin(admin.ModelAdmin):
    list_display = ("task", "event_type", "created_by", "created_at")
    list_filter = ("event_type", "task")
    search_fields = ("task__title",)