from django.urls import path

from .views import current_station_map, panel_detail

urlpatterns = [
    path("current/map", current_station_map, name="current-station-map"),
    path("panels/<int:panel_id>", panel_detail, name="panel-detail"),
]

