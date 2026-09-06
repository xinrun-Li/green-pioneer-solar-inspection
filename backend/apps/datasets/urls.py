from django.urls import path

from .views import (
    annotation_detail,
    asset_collection,
    asset_detail,
    create_annotation,
    freeze_version,
    reject_asset,
    submit_asset,
    version_collection,
)

urlpatterns = [
    path("dataset-assets/", asset_collection),
    path("dataset-assets/<int:asset_id>/", asset_detail),
    path("dataset-assets/<int:asset_id>/annotations/", create_annotation),
    path("dataset-assets/<int:asset_id>/submit/", submit_asset),
    path("dataset-assets/<int:asset_id>/reject/", reject_asset),
    path("annotations/<int:annotation_id>/", annotation_detail),
    path("dataset-versions/", version_collection),
    path("dataset-versions/<int:version_id>/freeze/", freeze_version),
]
