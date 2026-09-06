from django.contrib import admin

from .models import AgentAction, AgentConversation


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message", "intent", "status", "source", "confidence", "created_at")
    list_filter = ("intent", "status", "source")
    search_fields = ("message", "response")


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ("conversation", "action_type", "target", "result", "operator", "created_at")
    list_filter = ("action_type", "result")