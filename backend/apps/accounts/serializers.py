from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AuditLog, ControlOperator

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    display_name = serializers.CharField(min_length=2, max_length=80)
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        normalized = value.strip()
        existing = User.objects.filter(username__iexact=normalized).select_related("operator_profile").first()
        if existing:
            profile = getattr(existing, "operator_profile", None)
            if not profile or profile.review_status != ControlOperator.ReviewStatus.REJECTED:
                raise serializers.ValidationError("该账号已被注册")
            self.rejected_user = existing
        return normalized

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "两次输入的密码不一致"})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        rejected_user = getattr(self, "rejected_user", None)
        if rejected_user:
            rejected_user.set_password(validated_data["password"])
            rejected_user.first_name = validated_data["display_name"]
            rejected_user.is_active = True
            rejected_user.save(update_fields=("password", "first_name", "is_active"))
            profile = rejected_user.operator_profile
            profile.display_name = validated_data["display_name"]
            profile.phone = validated_data["phone"]
            profile.review_status = ControlOperator.ReviewStatus.PENDING
            profile.rejection_reason = ""
            profile.reviewed_by = None
            profile.reviewed_at = None
            profile.save(update_fields=(
                "display_name", "phone", "review_status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at",
            ))
            return rejected_user
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            first_name=validated_data["display_name"],
        )
        ControlOperator.objects.create(
            user=user, display_name=validated_data["display_name"], phone=validated_data["phone"],
            role=ControlOperator.Role.INSPECTOR,
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember = serializers.BooleanField(default=False)


class OperatorRoleField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        super().__init__(choices=ControlOperator.Role.choices, **kwargs)


class OperatorSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(source="review_status", read_only=True)
    action_label = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()
    station = serializers.SerializerMethodField()

    class Meta:
        model = ControlOperator
        fields = (
            "id", "user_id", "username", "display_name", "phone", "role", "status", "review_status", "action_label", "rejection_reason",
            "station", "reviewed_by", "reviewed_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "user_id", "username", "reviewed_by", "reviewed_at", "created_at", "updated_at")

    def get_reviewed_by(self, obj):
        if not obj.reviewed_by:
            return None
        return {"id": obj.reviewed_by_id, "username": obj.reviewed_by.username, "display_name": obj.reviewed_by.get_full_name()}

    def get_station(self, obj):
        if not obj.station:
            return None
        return {"id": obj.station_id, "name": obj.station.name}

    def get_action_label(self, obj):
        return obj.get_review_status_display()


class OperatorUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(min_length=2, max_length=80, required=False)
    phone = serializers.CharField(max_length=32, required=False)
    role = OperatorRoleField(required=False)
    status = serializers.ChoiceField(source="review_status", choices=ControlOperator.ReviewStatus.choices, required=False)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ReviewReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1, max_length=500)


class ApproveSerializer(serializers.Serializer):
    role = OperatorRoleField(required=False, default=ControlOperator.Role.INSPECTOR)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    password_confirm = serializers.CharField(write_only=True, min_length=8, required=False)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        if not attrs.get("password") and not attrs.get("password_confirm"):
            return attrs
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "两次输入的密码不一致"})
        validate_password(attrs["password"])
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    operator = serializers.SerializerMethodField()
    target_user = serializers.SerializerMethodField()
    action_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "operator", "action_type", "action_label", "target_user", "reason", "created_at")

    def get_action_label(self, obj):
        return obj.get_action_type_display()

    @staticmethod
    def _user_payload(user):
        if not user:
            return None
        return {"id": user.id, "username": user.username, "display_name": user.get_full_name() or user.username}

    def get_operator(self, obj):
        return self._user_payload(obj.operator)

    def get_target_user(self, obj):
        return self._user_payload(obj.target_user)
