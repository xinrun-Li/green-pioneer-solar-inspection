from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsApprovedOperator
from apps.inspections.models import InspectionTask

from .models import Report
from .serializers import ReportCreateSerializer, ReportDetailSerializer, ReportListSerializer
from .services import ReportGenerator, ReportRetryService, ReportSnapshotService


@api_view(["GET", "POST"])
@permission_classes([IsApprovedOperator])
def report_list(request):
    if request.method == "GET":
        reports = Report.objects.select_related("created_by").order_by("-created_at")
        if not request.user.is_superuser:
            reports = reports.filter(created_by=request.user)
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size
        queryset = reports[start:end]
        return Response({
            "count": reports.count(),
            "page": page,
            "page_size": page_size,
            "results": ReportListSerializer(queryset, many=True).data,
        })

    # POST
    serializer = ReportCreateSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    task_id = serializer.validated_data.pop("inspection_task_id")
    task = InspectionTask.objects.get(id=task_id)
    parameters = {
        **serializer.validated_data.pop("parameters", {}),
        "inspection_task_id": task.id,
        "inspection_task_title": task.title,
        "inspection_task_status": task.status,
    }
    report = serializer.save(created_by=request.user, parameters=parameters)

    # 收集快照数据并生成报告
    snapshot_data = ReportSnapshotService.collect(task)
    report.snapshot_data = snapshot_data
    report.save(update_fields=["snapshot_data"])

    ReportGenerator.generate(report)

    return Response(
        ReportDetailSerializer(report).data,
        status=201,
    )


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def report_detail(request, report_id):
    reports = Report.objects.select_related("created_by").filter(id=report_id)
    if not request.user.is_superuser:
        reports = reports.filter(created_by=request.user)
    report = reports.first()
    if report is None:
        return Response(
            {"code": "report_not_found", "message": "报告不存在"},
            status=404,
        )
    return Response(ReportDetailSerializer(report).data)


@api_view(["GET"])
@permission_classes([IsApprovedOperator])
def report_download(request, report_id):
    reports = Report.objects.filter(id=report_id)
    if not request.user.is_superuser:
        reports = reports.filter(created_by=request.user)
    report = reports.first()
    if report is None:
        return Response(
            {"code": "report_not_found", "message": "报告不存在"},
            status=404,
        )
    if report.status != Report.Status.READY:
        return Response(
            {"code": "report_not_ready", "message": "报告尚未就绪，无法下载"},
            status=400,
        )
    if not report.file:
        return Response(
            {"code": "report_no_file", "message": "报告文件不存在"},
            status=400,
        )
    return FileResponse(
        report.file.open("rb"),
        as_attachment=True,
        filename=report.file.name.split("/")[-1],
    )


@api_view(["POST"])
@permission_classes([IsApprovedOperator])
def report_retry(request, report_id):
    reports = Report.objects.filter(id=report_id)
    if not request.user.is_superuser:
        reports = reports.filter(created_by=request.user)
    report = reports.first()
    if report is None:
        return Response(
            {"code": "report_not_found", "message": "报告不存在"},
            status=404,
        )
    ReportRetryService.retry(report)
    return Response(ReportDetailSerializer(report).data)
