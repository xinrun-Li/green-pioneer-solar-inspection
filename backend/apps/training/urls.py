from django.urls import path

from .views import (
    activate,
    cancel_run,
    model_collection,
    model_detail,
    rollback,
    run_collection,
    run_detail,
    run_logs,
    run_metrics,
)

urlpatterns = [
    path("model-versions/", model_collection),
    path("model-versions/<int:model_id>/", model_detail),
    path("model-versions/<int:model_id>/activate/", activate),
    path("model-versions/<int:model_id>/rollback/", rollback),
    path("training-runs/", run_collection),
    path("training-runs/<int:run_id>/", run_detail),
    path("training-runs/<int:run_id>/cancel/", cancel_run),
    path("training-runs/<int:run_id>/logs/", run_logs),
    path("training-runs/<int:run_id>/metrics/", run_metrics),
]
