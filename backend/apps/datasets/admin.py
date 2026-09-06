from django.contrib import admin

from .models import Annotation, DatasetAsset, DatasetVersion


@admin.register(DatasetAsset)
class DatasetAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "original_name", "annotation_status", "source_type", "is_hard_sample", "created_at")
    list_filter = ("annotation_status", "source_type", "is_hard_sample")


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ("asset", "class_name", "source", "operator", "created_at")
    list_filter = ("class_name", "source")


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "status", "train_count", "validation_count", "test_count", "created_at")
    list_filter = ("status",)
