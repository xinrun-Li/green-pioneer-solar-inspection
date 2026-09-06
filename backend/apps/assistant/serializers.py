from rest_framework import serializers

from .models import AgentAction, AgentConversation
from .services import INTENT_DEFINITIONS


def _intent_label(intent: str) -> str:
    if intent == "chat":
        return "智能对话"
    return INTENT_DEFINITIONS.get(intent, {}).get("label", intent or "未知意图")


class AgentActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAction
        fields = "__all__"
        read_only_fields = ("created_at",)


class ConversationListSerializer(serializers.ModelSerializer):
    intent_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = AgentConversation
        fields = (
            "id", "message", "intent", "intent_display", "status",
            "status_display", "source", "source_display", "confidence",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "intent", "intent_display", "status", "status_display",
            "source", "source_display", "confidence", "created_at", "updated_at",
        )

    def get_intent_display(self, obj):
        return _intent_label(obj.intent)


class ConversationDetailSerializer(serializers.ModelSerializer):
    actions = AgentActionSerializer(many=True, read_only=True)
    intent_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = AgentConversation
        fields = (
            "id", "message", "intent", "intent_display", "slots",
            "response", "draft_action", "status", "status_display",
            "source", "source_display", "confidence", "error_message",
            "actions", "created_at", "updated_at",
        )
        read_only_fields = [f.name for f in AgentConversation._meta.fields] + ["actions"]

    def get_intent_display(self, obj):
        return _intent_label(obj.intent)


class ConversationCreateSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, min_length=1)


class DraftConfirmSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["confirm", "reject", "retry"])
