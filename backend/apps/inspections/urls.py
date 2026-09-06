from django.urls import path

from . import views

urlpatterns = [
    path("", views.task_list, name="inspection-task-list"),
    path("history/", views.history_list, name="inspection-history-list"),
    path("manual-check/", views.manual_check, name="inspection-manual-check"),
    path("<int:task_id>/", views.task_detail, name="inspection-task-detail"),
    path("create/", views.create_task, name="inspection-task-create"),
    path("<int:task_id>/confirm/", views.confirm_task, name="inspection-task-confirm"),
    path("<int:task_id>/start/", views.start_task, name="inspection-task-start"),
    path("<int:task_id>/pause/", views.pause_task, name="inspection-task-pause"),
    path("<int:task_id>/resume/", views.resume_task, name="inspection-task-resume"),
    path("<int:task_id>/cancel/", views.cancel_task, name="inspection-task-cancel"),
    path("<int:task_id>/simulate/", views.simulate_execute_view, name="inspection-task-simulate"),
    path("<int:task_id>/waypoints/<int:waypoint_id>/skip/", views.skip_waypoint, name="inspection-waypoint-skip"),
    path("<int:task_id>/events/", views.task_events, name="inspection-task-events"),
]
