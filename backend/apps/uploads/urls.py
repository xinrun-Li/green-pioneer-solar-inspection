from django.urls import path

from .views import batch_collection, upload_media

urlpatterns = [
    path("", batch_collection, name="upload-batches"),
    path("<int:batch_id>/media", upload_media, name="upload-media"),
]

