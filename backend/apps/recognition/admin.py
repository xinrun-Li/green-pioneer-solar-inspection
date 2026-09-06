from django.contrib import admin

from .models import Detection, RecognitionJob, ReviewAction


@admin.register(RecognitionJob)
class RecognitionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "media", "status", "progress", "adapter", "is_demo_data", "created_at")
    list_filter = ("status", "adapter", "is_demo_data")


@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = ("job", "sequence", "model_class", "original_class", "confirmed_class", "confidence", "review_status")
    list_filter = ("original_class", "review_status", "is_demo_data")


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ("detection", "operator", "previous_class", "confirmed_class", "created_at")
    list_filter = ("confirmed_class",)
