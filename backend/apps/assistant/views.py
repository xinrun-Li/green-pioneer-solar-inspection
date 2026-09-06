from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.inspections.models import InspectionTask
from apps.inspections.services import generate_s_route
from apps.reports.models import Report
from apps.reports.services import ReportGenerator, ReportSnapshotService
from apps.stations.models import Station

from .deepseek import DeepSeekError, generate_deepseek_reply, is_deepseek_configured
from .models import AgentAction, AgentConversation
from .serializers import (
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    DraftConfirmSerializer,
)
from .services import IntentEngine, generate_draft

engine = IntentEngine()

# Read-only queries and page navigation should feel immediate. Only actions
# that change data or create an export need an explicit confirmation step.
CONFIRMABLE_ACTION_TYPES = {"create", "update", "export"}


@api_view(["POST"])
def assistant_query(request):
    """用户发送消息 → 本地业务意图或 DeepSeek 普通对话。"""
    user = request.user
    perm = IsApprovedOperator()
    if not perm.has_permission(request, None):
        return Response({"detail": "无权限"}, status=status.HTTP_403_FORBIDDEN)

    serializer = ConversationCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    message = serializer.validated_data["message"]

    # 1. 使用本地规则引擎进行意图分类
    intent, slots, confidence = engine.classify(message)

    error_msg = ""
    conversation_status = AgentConversation.Status.PENDING

    # 未命中业务关键词时交给 DeepSeek。业务查询仍由本地数据库生成。
    if confidence <= 0.3:
        intent = "chat"
        slots = {}
        draft_action = None
        source = AgentConversation.Source.CLOUD
        try:
            response_text = generate_deepseek_reply(user, message)
            confidence = 1.0
        except DeepSeekError as exc:
            response_text = str(exc)
            confidence = 0.0
            error_msg = str(exc)
            conversation_status = AgentConversation.Status.FAILED
    else:
        try:
            draft = generate_draft(intent, slots, user)
            response_text = draft["response"]
            candidate_action = {k: v for k, v in draft.items() if k != "response"}
            draft_action = (
                candidate_action
                if candidate_action.get("action_type") in CONFIRMABLE_ACTION_TYPES
                else None
            )
            source = AgentConversation.Source.LOCAL
            conversation_status = AgentConversation.Status.DRAFTED if draft_action else AgentConversation.Status.PENDING
        except Exception as exc:
            response_text = "本地巡检数据暂时无法读取，请稍后重试。"
            draft_action = None
            source = AgentConversation.Source.LOCAL
            confidence = 0.0
            error_msg = str(exc)
            conversation_status = AgentConversation.Status.FAILED

    # 3. 保存对话
    conversation = AgentConversation.objects.create(
        user=user,
        message=message,
        intent=intent,
        slots=slots,
        response=response_text,
        draft_action=draft_action,
        source=source,
        confidence=confidence,
        error_message=error_msg,
        status=conversation_status,
    )

    return Response(ConversationDetailSerializer(conversation).data)


@api_view(["GET"])
def assistant_status(request):
    """返回助手提供方配置状态，不向前端泄露 API Key。"""
    perm = IsApprovedOperator()
    if not perm.has_permission(request, None):
        return Response({"detail": "无权限"}, status=status.HTTP_403_FORBIDDEN)
    return Response({
        "provider": "DeepSeek",
        "model": getattr(settings, "DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "configured": is_deepseek_configured(),
    })


@api_view(["POST"])
def assistant_confirm(request):
    """确认/拒绝/重试草稿"""
    user = request.user
    perm = IsApprovedOperator()
    if not perm.has_permission(request, None):
        return Response({"detail": "无权限"}, status=status.HTTP_403_FORBIDDEN)

    serializer = DraftConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_id = serializer.validated_data["conversation_id"]
    action = serializer.validated_data["action"]

    try:
        conversation = AgentConversation.objects.get(pk=conv_id, user=user)
    except AgentConversation.DoesNotExist:
        return Response({"detail": "对话不存在"}, status=status.HTTP_404_NOT_FOUND)

    if conversation.status != AgentConversation.Status.DRAFTED:
        return Response(
            {"detail": f"当前状态为 {conversation.get_status_display()}，无法操作"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action == "confirm":
        # 执行草稿动作
        with transaction.atomic():
            result = _execute_draft(conversation, user)
            conversation.status = AgentConversation.Status.CONFIRMED if result.get("success") else AgentConversation.Status.FAILED
            conversation.response = result.get("message", conversation.response)
            conversation.save(update_fields=("status", "response", "updated_at"))

            AgentAction.objects.create(
                conversation=conversation,
                action_type=conversation.draft_action.get("action_type", "query"),
                target=conversation.draft_action.get("target", ""),
                payload=conversation.draft_action.get("payload", {}),
                result=AgentAction.Result.SUCCESS if result.get("success") else AgentAction.Result.FAILED,
                result_data=result,
                operator=user,
            )

        return Response({
            "success": result.get("success"),
            "message": result.get("message", "执行成功"),
            "conversation": ConversationDetailSerializer(conversation).data,
        })

    elif action == "reject":
        conversation.status = AgentConversation.Status.REJECTED
        conversation.save()
        return Response({
            "success": True,
            "message": "已拒绝",
            "conversation": ConversationDetailSerializer(conversation).data,
        })

    elif action == "retry":
        # 重新生成草稿
        intent, slots, confidence = engine.classify(conversation.message)
        try:
            draft = generate_draft(intent, slots, user)
            conversation.response = draft["response"]
            candidate_action = {k: v for k, v in draft.items() if k != "response"}
            conversation.draft_action = (
                candidate_action
                if candidate_action.get("action_type") in CONFIRMABLE_ACTION_TYPES
                else None
            )
            conversation.intent = intent
            conversation.slots = slots
            conversation.confidence = confidence
            conversation.source = AgentConversation.Source.LOCAL
            conversation.error_message = ""
            conversation.status = (
                AgentConversation.Status.DRAFTED
                if conversation.draft_action
                else AgentConversation.Status.PENDING
            )
        except Exception as e:
            conversation.response = f"重试失败：{e!s}"
            conversation.source = AgentConversation.Source.CLOUD
            conversation.confidence = 0.0
            conversation.error_message = str(e)
            conversation.status = AgentConversation.Status.PENDING
        conversation.save()
        return Response({
            "success": True,
            "message": "已重新生成草稿",
            "conversation": ConversationDetailSerializer(conversation).data,
        })

    return Response({"detail": "无效操作"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def assistant_conversations(request):
    """对话历史列表"""
    user = request.user
    perm = IsApprovedOperator()
    if not perm.has_permission(request, None):
        return Response({"detail": "无权限"}, status=status.HTTP_403_FORBIDDEN)
    conversations = AgentConversation.objects.filter(user=user)[:50]
    return Response(ConversationDetailSerializer(conversations, many=True).data)


@api_view(["GET"])
def assistant_conversation_detail(request, conv_id):
    """单条对话详情"""
    user = request.user
    perm = IsApprovedOperator()
    if not perm.has_permission(request, None):
        return Response({"detail": "无权限"}, status=status.HTTP_403_FORBIDDEN)
    try:
        conv = AgentConversation.objects.get(pk=conv_id, user=user)
    except AgentConversation.DoesNotExist:
        return Response({"detail": "不存在"}, status=status.HTTP_404_NOT_FOUND)
    return Response(ConversationDetailSerializer(conv).data)


def _execute_draft(conversation: AgentConversation, user) -> dict:
    """执行草稿动作"""
    draft = conversation.draft_action
    if not draft:
        return {"success": False, "message": "无草稿动作"}

    action_type = draft.get("action_type", "query")
    target = draft.get("target", "")
    payload = draft.get("payload", {})

    if action_type == "navigate":
        return {"success": True, "message": f"跳转至「{target}」", "page": payload.get("page")}

    if action_type == "update":
        task_id = payload.get("task_id")
        action = payload.get("action")
        if task_id and action:
            try:
                task = InspectionTask.objects.get(pk=task_id)
                if action == "start":
                    if task.status != InspectionTask.Status.CONFIRMED:
                        return {"success": False, "message": f"任务状态为 {task.get_status_display()}，无法启动"}
                    task.status = InspectionTask.Status.RUNNING
                    task.started_at = timezone.now()
                    task.save()
                    return {"success": True, "message": f"任务「{task.title}」已启动"}
                elif action == "pause":
                    if task.status != InspectionTask.Status.RUNNING:
                        return {"success": False, "message": f"任务状态为 {task.get_status_display()}，无法暂停"}
                    task.status = InspectionTask.Status.PAUSED
                    task.save()
                    return {"success": True, "message": f"任务「{task.title}」已暂停"}
            except InspectionTask.DoesNotExist:
                return {"success": False, "message": "任务不存在"}

    if action_type == "export":
        if target == "巡检报告":
            format_names = {"网页": "web", "Excel": "excel", "PDF": "pdf"}
            requested_format = str(payload.get("format", "网页"))
            formats = ["web", "excel", "pdf"] if requested_format == "全部" else [format_names.get(requested_format, "web")]
            task_id = payload.get("task_id")
            task = InspectionTask.objects.filter(id=task_id, status=InspectionTask.Status.COMPLETED).first() if task_id else None
            if task is None:
                return {"success": False, "message": "请先指定一个已完成的巡检任务，再生成分析报告"}
            reports = []
            snapshot = ReportSnapshotService.collect(task)
            for report_type in formats:
                report = Report.objects.create(
                    report_type=report_type,
                    parameters={
                        "source": "assistant", "period": payload.get("period", "本月"),
                        "inspection_task_id": task.id, "inspection_task_title": task.title,
                        "inspection_task_status": task.status,
                    },
                    filters={"station": payload.get("station", "全部")},
                    snapshot_data=snapshot,
                    created_by=user,
                )
                ReportGenerator.generate(report)
                reports.append({"id": report.id, "report_type": report.report_type, "status": report.status})
            failed = [item for item in reports if item["status"] != Report.Status.READY]
            if failed:
                return {
                    "success": False,
                    "message": "部分报告生成失败，请到报告中心查看失败原因",
                    "redirect": "reports", "reports": reports,
                }
            return {
                "success": True,
                "message": f"已生成 {len(reports)} 份巡检分析报告，请到报告中心查看",
                "redirect": "reports",
                "reports": reports,
            }
        return {"success": True, "message": f"导出「{target}」任务已提交"}

    if action_type == "create":
        if target == "巡检任务":
            station_id = payload.get("station_id")
            title = str(payload.get("title") or "助手创建的巡检任务").strip()
            if not station_id:
                return {"success": False, "message": "未找到可用电站，请先在系统中初始化演示电站"}
            station = Station.objects.filter(id=station_id, is_active=True).first()
            if station is None:
                return {"success": False, "message": "目标电站不存在或已停用"}
            scope = " ".join(filter(None, [str(payload.get("region", "")).strip(), str(payload.get("array_code", "")).strip()]))
            description = f"由绿能助手创建。巡检范围：{scope or '全站'}。"
            task = InspectionTask.objects.create(
                title=title[:200], description=description, station=station, created_by=user,
            )
            generate_s_route(task)
            from apps.inspections.models import InspectionEvent
            InspectionEvent.objects.create(
                task=task, event_type=InspectionEvent.EventType.CREATED,
                description=f"助手确认创建任务，共 {task.total_waypoints} 个航点", created_by=user,
            )
            return {
                "success": True,
                "message": f"巡检任务「{task.title}」已创建，共 {task.total_waypoints} 个航点，请到任务中心确认执行",
                "redirect": "tasks", "task_id": task.id, "total_waypoints": task.total_waypoints,
            }

    # query 类动作直接返回
    return {"success": True, "message": conversation.response.split("。")[0] + "。"}
