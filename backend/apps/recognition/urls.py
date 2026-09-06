from django.urls import path

from .views import create_job, job_detail, retry_job, run_job, run_mock

urlpatterns = [
    path("", create_job, name="create-recognition-job"),
    path("<int:job_id>", job_detail, name="recognition-job-detail"),
    path("<int:job_id>/run-mock", run_mock, name="run-mock-recognition"),
    path("<int:job_id>/run/", run_job, name="run-recognition"),
    path("<int:job_id>/retry", retry_job, name="retry-recognition-job"),
]
