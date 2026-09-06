from django.urls import path

from . import views

urlpatterns = [
    path("", views.report_list, name="report-list"),
    path("<int:report_id>/", views.report_detail, name="report-detail"),
    path("<int:report_id>/download/", views.report_download, name="report-download"),
    path("<int:report_id>/retry/", views.report_retry, name="report-retry"),
]