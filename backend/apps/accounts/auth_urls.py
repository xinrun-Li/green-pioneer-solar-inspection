from django.urls import path

from .views import login_view, logout_view, mark_notifications_read_view, me_view, notification_list_view, register_view

urlpatterns = [
    path("register", register_view, name="register"),
    path("register/", register_view, name="register-slash"),
    path("login", login_view, name="login"),
    path("logout", logout_view, name="logout"),
    path("me", me_view, name="me"),
    path("notifications", notification_list_view, name="notifications"),
    path("notifications/read", mark_notifications_read_view, name="notifications-read"),
]
