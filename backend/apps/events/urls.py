from django.urls import path

from .views import close_event, event_detail, event_list, panel_events

urlpatterns = [
    path("", event_list, name="event-list"),
    path("<int:event_id>", event_detail, name="event-detail"),
    path("<int:event_id>/close", close_event, name="event-close"),
    path("by-panel/<int:panel_id>", panel_events, name="panel-events"),
]