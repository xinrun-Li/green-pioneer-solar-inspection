from django.contrib import admin

from .models import MediaAsset, UploadBatch


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "creator", "station", "status", "created_at")
    list_filter = ("status", "station")
    search_fields = ("creator__username", "region_note")


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("original_name", "kind", "batch", "status", "size_bytes", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("original_name", "checksum")

