from django.urls import path

from .views import review_detection

urlpatterns = [path("<int:detection_id>/review", review_detection, name="review-detection")]

