from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status

from apps.accounts.models import ControlOperator
from apps.inspections.models import InspectionTask
from apps.stations.models import Station

from .models import Report


class ReportAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operator",
            password="testpass123",
            is_active=True,
        )
        # 创建经审核通过的 ControlOperator，满足 IsApprovedOperator 权限
        ControlOperator.objects.create(
            user=self.user,
            display_name="测试操作员",
            station=Station.objects.create(code="REPORT", name="报告测试电站"),
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        self.task = InspectionTask.objects.create(
            title="已完成巡检结果", station=self.user.operator_profile.station,
            status=InspectionTask.Status.COMPLETED, created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_list_reports_get(self):
        """测试 GET report_list 返回空列表"""
        response = self.client.get("/api/v1/reports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_create_report(self):
        """测试 POST 创建报告并生成"""
        response = self.client.post(
            "/api/v1/reports/",
            {"report_type": "web", "inspection_task_id": self.task.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        # 验证报告状态
        report_id = response.data["id"]
        report = Report.objects.get(id=report_id)
        self.assertIn(report.status, [Report.Status.READY, Report.Status.FAILED])
        self.assertEqual(report.parameters["inspection_task_id"], self.task.id)
        self.assertEqual(response.data["inspection_task_title"], self.task.title)

    def test_report_requires_completed_inspection_task(self):
        draft = InspectionTask.objects.create(
            title="未完成结果", station=self.user.operator_profile.station,
            status=InspectionTask.Status.DRAFT, created_by=self.user,
        )
        response = self.client.post(
            "/api/v1/reports/", {"report_type": "web", "inspection_task_id": draft.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_detail(self):
        """测试 GET report_detail"""
        report = Report.objects.create(
            report_type=Report.ReportType.WEB,
            status=Report.Status.READY,
            created_by=self.user,
        )
        response = self.client.get(f"/api/v1/reports/{report.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], report.id)

    def test_report_download_no_file(self):
        """测试下载无文件的报告返回 400"""
        report = Report.objects.create(
            report_type=Report.ReportType.WEB,
            status=Report.Status.READY,
            created_by=self.user,
        )
        response = self.client.get(f"/api/v1/reports/{report.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
