from django.contrib import admin

from .models import ModelVersion, TrainingRun


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ("version", "model_type", "status", "is_active", "model_sha256", "dataset_version", "activated_at")
    list_filter = ("model_type", "status", "is_active")


@admin.register(TrainingRun)
class TrainingRunAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset_version", "status", "progress", "device", "created_at")
    list_filter = ("status", "device")
