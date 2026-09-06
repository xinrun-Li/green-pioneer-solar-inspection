import secrets

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.middleware.csrf import get_token
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import AccountNotification, AuditLog, ControlOperator
from .permissions import IsAccountManager
from .serializers import (
    ApproveSerializer,
    AuditLogSerializer,
    LoginSerializer,
    OperatorSerializer,
    OperatorUpdateSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    ReviewReasonSerializer,
)


def user_payload(user):
    profile = getattr(user, "operator_profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": profile.display_name if profile else user.get_full_name() or user.username,
        "phone": profile.phone if profile else "",
        "role": profile.role if profile else (ControlOperator.Role.ADMIN if user.is_superuser else ControlOperator.Role.INSPECTOR),
        "review_status": profile.review_status if profile else ("approved" if user.is_superuser else "pending"),
        "rejection_reason": profile.rejection_reason if profile else "",
        "is_restricted": bool(profile and not user.is_active and not user.is_superuser),
        "station": ({"id": profile.station_id, "name": profile.station.name} if profile and profile.station else None),
        "is_admin": user.is_staff,
        "is_account_manager": bool(
            user.is_superuser or user.is_staff or (profile and profile.role in {
                ControlOperator.Role.ADMIN,
                ControlOperator.Role.REVIEWER,
            })
        ),
        "is_superuser": user.is_superuser,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    action_type = AuditLog.ActionType.EDIT if hasattr(serializer, "rejected_user") else AuditLog.ActionType.CREATE
    _audit(user, action_type, user, "前台注册" if action_type == AuditLog.ActionType.CREATE else "驳回后重新提交")
    return Response({"code": "registration_pending", "message": "注册成功，请等待管理员审核"}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(request, username=serializer.validated_data["username"], password=serializer.validated_data["password"])
    if user is None:
        return Response({"code": "invalid_credentials", "message": "账号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)

    profile = getattr(user, "operator_profile", None)
    if not user.is_superuser:
        state = profile.review_status if profile else ControlOperator.ReviewStatus.PENDING
        if state == ControlOperator.ReviewStatus.PENDING:
            return Response({"code": "registration_pending", "message": "账户正在等待管理员审核"}, status=status.HTTP_403_FORBIDDEN)
        if state == ControlOperator.ReviewStatus.REJECTED:
            return Response({"code": "registration_rejected", "message": profile.rejection_reason or "注册申请未通过，请联系管理员"}, status=status.HTTP_403_FORBIDDEN)
        if state == ControlOperator.ReviewStatus.DISABLED or not user.is_active:
            return Response({"code": "account_disabled", "message": "账户已停用，请联系管理员"}, status=status.HTTP_403_FORBIDDEN)

    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 14 if serializer.validated_data["remember"] else 0)
    return Response({"user": user_payload(user), "csrf_token": get_token(request)})


def _audit(actor, action_type, target_user, reason=""):
    return AuditLog.objects.create(
        operator=actor, action_type=action_type, target_user=target_user, reason=reason.strip() or "后台操作",
    )


def _notify_account(user, kind, title, content):
    return AccountNotification.objects.create(user=user, kind=kind, title=title, content=content)


def _operator_response(profile, http_status=status.HTTP_200_OK):
    return Response(OperatorSerializer(profile).data, status=http_status)


@api_view(["GET"])
@permission_classes([IsAccountManager])
def operator_list_view(request):
    queryset = ControlOperator.objects.select_related("user", "reviewed_by", "station")
    review_status = request.query_params.get("status")
    role = request.query_params.get("role")
    search = request.query_params.get("search", "").strip()
    if review_status:
        queryset = queryset.filter(review_status=review_status)
    if role:
        queryset = queryset.filter(role=role)
    if search:
        queryset = queryset.filter(Q(display_name__icontains=search) | Q(phone__icontains=search) | Q(user__username__icontains=search))
    queryset = queryset.annotate(
        pending_first=Case(When(review_status=ControlOperator.ReviewStatus.PENDING, then=Value(0)), default=Value(1), output_field=IntegerField())
    ).order_by("pending_first", "-created_at")
    return Response({"count": queryset.count(), "results": OperatorSerializer(queryset, many=True).data})


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAccountManager])
def operator_detail_view(request, operator_id):
    profile = ControlOperator.objects.select_related("user", "reviewed_by", "station").filter(pk=operator_id).first()
    if profile is None:
        return Response({"code": "operator_not_found", "message": "控制人员不存在"}, status=404)
    if request.method == "GET":
        payload = OperatorSerializer(profile).data
        payload["audit_logs"] = AuditLogSerializer(
            AuditLog.objects.filter(target_user=profile.user).select_related("operator", "target_user"), many=True,
        ).data
        return Response(payload)
    if request.method == "DELETE":
        if not request.user.is_superuser:
            return Response({"code": "superuser_required", "message": "只有超级管理员可以彻底删除账号"}, status=403)
        reason = str(request.data.get("reason", "")).strip()
        target_user = profile.user
        with transaction.atomic():
            _audit(request.user, AuditLog.ActionType.DELETE, target_user, reason)
            target_user.delete()
        return Response(status=204)

    serializer = OperatorUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    changes = serializer.validated_data
    reason = changes.pop("reason", "")
    changed_fields = []
    role_changed = "role" in changes and changes["role"] != profile.role
    for field in ("display_name", "phone", "role"):
        if field in changes:
            setattr(profile, field, changes[field])
            changed_fields.append(field)
    if "review_status" in changes:
        profile.review_status = changes["review_status"]
        if profile.review_status in {
            ControlOperator.ReviewStatus.APPROVED,
            ControlOperator.ReviewStatus.REJECTED,
        }:
            profile.reviewed_by = request.user
            profile.reviewed_at = now()
        profile.user.is_active = profile.review_status != ControlOperator.ReviewStatus.DISABLED
        profile.user.save(update_fields=("is_active",))
        changed_fields.append("review_status")
        changed_fields.extend(("reviewed_by", "reviewed_at"))
    if not changed_fields:
        return _operator_response(profile)
    with transaction.atomic():
        profile.save(update_fields=(*tuple(changed_fields), "updated_at"))
        _audit(request.user, AuditLog.ActionType.ROLE_CHANGE if role_changed else AuditLog.ActionType.EDIT, profile.user, reason)
    return _operator_response(profile)


@api_view(["POST"])
@permission_classes([IsAccountManager])
def approve_operator_view(request, operator_id):
    profile = ControlOperator.objects.select_related("user").filter(pk=operator_id).first()
    if profile is None:
        return Response({"code": "operator_not_found", "message": "控制人员不存在"}, status=404)
    serializer = ApproveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        profile.role = serializer.validated_data["role"]
        profile.review_status = ControlOperator.ReviewStatus.APPROVED
        profile.rejection_reason = ""
        profile.reviewed_by = request.user
        profile.reviewed_at = now()
        profile.save(update_fields=("role", "review_status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"))
        profile.user.is_active = True
        profile.user.save(update_fields=("is_active",))
        _audit(request.user, AuditLog.ActionType.APPROVE, profile.user, serializer.validated_data.get("reason", ""))
        _notify_account(
            profile.user,
            AccountNotification.Kind.APPROVED,
            "注册申请已通过",
            f"管理员已通过你的注册申请，当前业务角色为{profile.get_role_display()}。现在可以进入巡检控制台。",
        )
    return _operator_response(profile)


@api_view(["POST"])
@permission_classes([IsAccountManager])
def reject_operator_view(request, operator_id):
    profile = ControlOperator.objects.select_related("user").filter(pk=operator_id).first()
    if profile is None:
        return Response({"code": "operator_not_found", "message": "控制人员不存在"}, status=404)
    serializer = ReviewReasonSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = serializer.validated_data["reason"]
    with transaction.atomic():
        profile.review_status = ControlOperator.ReviewStatus.REJECTED
        profile.rejection_reason = reason
        profile.reviewed_by = request.user
        profile.reviewed_at = now()
        profile.save(update_fields=("review_status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"))
        profile.user.is_active = True
        profile.user.save(update_fields=("is_active",))
        _audit(request.user, AuditLog.ActionType.REJECT, profile.user, reason)
        _notify_account(
            profile.user,
            AccountNotification.Kind.REJECTED,
            "注册申请需要修改",
            f"管理员驳回了你的注册申请，原因：{reason}。请修改资料后重新提交。",
        )
    return _operator_response(profile)


def _set_operator_status(request, operator_id, action):
    profile = ControlOperator.objects.select_related("user").filter(pk=operator_id).first()
    if profile is None:
        return Response({"code": "operator_not_found", "message": "控制人员不存在"}, status=404)
    reason = str(request.data.get("reason", "")).strip()
    next_status = ControlOperator.ReviewStatus.DISABLED if action == "disable" else ControlOperator.ReviewStatus.APPROVED
    with transaction.atomic():
        profile.review_status = next_status
        if action == "restore":
            profile.reviewed_by = request.user
            profile.reviewed_at = now()
        profile.save(update_fields=("review_status", "reviewed_by", "reviewed_at", "updated_at"))
        profile.user.is_active = action == "restore"
        profile.user.save(update_fields=("is_active",))
        _audit(request.user, AuditLog.ActionType.DISABLE, profile.user, reason or ("恢复账号" if action == "restore" else "停用账号"))
    return _operator_response(profile)


@api_view(["POST"])
@permission_classes([IsAccountManager])
def disable_operator_view(request, operator_id):
    return _set_operator_status(request, operator_id, "disable")


@api_view(["POST"])
@permission_classes([IsAccountManager])
def restore_operator_view(request, operator_id):
    return _set_operator_status(request, operator_id, "restore")


@api_view(["POST"])
@permission_classes([IsAccountManager])
def reset_password_view(request, operator_id):
    profile = ControlOperator.objects.select_related("user").filter(pk=operator_id).first()
    if profile is None:
        return Response({"code": "operator_not_found", "message": "控制人员不存在"}, status=404)
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    temporary_password = None
    password = serializer.validated_data.get("password")
    if not password:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        temporary_password = "Gp-" + "".join(secrets.choice(alphabet) for _ in range(13)) + "!"
        password = temporary_password
    profile.user.set_password(password)
    profile.user.save(update_fields=("password",))
    _audit(request.user, AuditLog.ActionType.RESET_PASSWORD, profile.user, serializer.validated_data.get("reason", ""))
    payload = {"message": "密码已重置"}
    if temporary_password:
        payload["temporary_password"] = temporary_password
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAccountManager])
def audit_log_list_view(request):
    queryset = AuditLog.objects.select_related("operator", "target_user")
    operator = request.query_params.get("operator")
    search = request.query_params.get("search", "").strip()
    action_type = request.query_params.get("action_type")
    date_from = parse_date(request.query_params.get("date_from", ""))
    date_to = parse_date(request.query_params.get("date_to", ""))
    if operator:
        operator_filter = (
            Q(operator__username__iexact=operator)
            | Q(operator__first_name__icontains=operator)
            | Q(operator__last_name__icontains=operator)
            | Q(operator__operator_profile__display_name__icontains=operator)
        )
        if operator.isdigit():
            operator_filter |= Q(operator_id=int(operator))
        queryset = queryset.filter(operator_filter)
    if search:
        queryset = queryset.filter(
            Q(operator__username__icontains=search)
            | Q(operator__first_name__icontains=search)
            | Q(operator__last_name__icontains=search)
            | Q(operator__operator_profile__display_name__icontains=search)
            | Q(target_user__username__icontains=search)
            | Q(target_user__first_name__icontains=search)
            | Q(target_user__last_name__icontains=search)
            | Q(target_user__operator_profile__display_name__icontains=search)
            | Q(reason__icontains=search)
        )
    if action_type:
        queryset = queryset.filter(action_type=action_type)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return Response({"count": queryset.count(), "results": AuditLogSerializer(queryset, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list_view(request):
    queryset = AccountNotification.objects.filter(user=request.user)
    unread = queryset.filter(is_read=False).count()
    return Response({
        "unread_count": unread,
        "results": [
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "content": item.content,
                "is_read": item.is_read,
                "created_at": item.created_at,
            }
            for item in queryset[:20]
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notifications_read_view(request):
    updated = AccountNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"updated": updated})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"message": "已退出登录"})


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    csrf_token = get_token(request)
    if not request.user.is_authenticated:
        return Response({"authenticated": False, "csrf_token": csrf_token})
    return Response({"authenticated": True, "user": user_payload(request.user), "csrf_token": csrf_token})
