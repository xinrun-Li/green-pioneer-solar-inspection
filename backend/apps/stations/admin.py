from django.contrib import admin

from .models import Panel, PanelStatusHistory, Region, SolarArray, Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "station", "direction", "sort_order")
    list_filter = ("station", "direction")


@admin.register(SolarArray)
class SolarArrayAdmin(admin.ModelAdmin):
    list_display = ("code", "region", "rows", "columns")
    list_filter = ("region__station", "region")


@admin.register(Panel)
class PanelAdmin(admin.ModelAdmin):
    list_display = ("full_code", "short_code", "array", "row", "column", "current_status")
    list_filter = ("current_status", "array__region", "array")
    search_fields = ("full_code", "short_code")


@admin.register(PanelStatusHistory)
class PanelStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("panel", "status", "reason", "recorded_at")
    list_filter = ("status", "panel__array__region")
    search_fields = ("panel__full_code", "panel__short_code")
    date_hierarchy = "recorded_at"

