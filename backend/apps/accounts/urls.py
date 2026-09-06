from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.management_urls")),
]
