from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.assistant_status, name="assistant-status"),
    path("query/", views.assistant_query, name="assistant-query"),
    path("confirm/", views.assistant_confirm, name="assistant-confirm"),
    path("conversations/", views.assistant_conversations, name="assistant-conversations"),
    path("conversations/<int:conv_id>/", views.assistant_conversation_detail, name="assistant-conversation-detail"),
]
