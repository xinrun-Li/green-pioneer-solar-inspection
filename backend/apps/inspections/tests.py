from django.test import TestCase

from django.contrib.auth import get_user_model
from apps.accounts.models import ControlOperator
from apps.stations.models import Panel, Region, SolarArray, Station

from .models import InspectionRecord, InspectionTask


class InspectionTaskApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="task-owner", password="ValidPass_2026!")
        station = Station.objects.create(code="TASK", name="任务测试电站")
        ControlOperator.objects.create(
            user=self.user, display_name="任务测试员", station=station,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        region = Region.objects.create(station=station, name="北区", direction=Region.Direction.NORTH, sort_order=1)
        array = SolarArray.objects.create(region=region, code="A1", rows=1, columns=1)
        self.panel = Panel.objects.create(array=array, full_code="A1-R01-C01", short_code="A1-001", row=1, column=1)
        self.client.force_login(self.user)
        self.station = station

    def test_create_task_returns_detail_instead_of_500(self):
        response = self.client.post(
            "/api/v1/inspections/create/",
            {"title": "北区测试巡检", "station_id": self.station.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["created_by_name"], "任务测试员")
        self.assertEqual(response.json()["total_waypoints"], 1)

    def test_manual_check_creates_history_record(self):
        response = self.client.post(
            "/api/v1/inspections/manual-check/",
            {"panel_id": self.panel.id, "status": "cleaning", "note": "发现积灰"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["record"]["source"], "manual")
        self.assertEqual(response.json()["record"]["status"], "cleaning")
        self.assertEqual(InspectionRecord.objects.filter(source=InspectionRecord.Source.MANUAL).count(), 1)
        self.panel.refresh_from_db()
        self.assertEqual(self.panel.current_status, Panel.Status.CLEANING)

    def test_history_endpoint_returns_records(self):
        InspectionRecord.objects.create(
            panel=self.panel, operator=self.user, source=InspectionRecord.Source.MANUAL,
            status=Panel.Status.NORMAL, summary="手动检查：正常",
        )
        response = self.client.get("/api/v1/inspections/history/?source=manual")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["stats"]["manual_records"], 1)
        self.assertEqual(payload["results"][0]["panel_full_code"], "A1-R01-C01")

    def test_task_execution_creates_history_record_even_when_media_is_missing(self):
        created = self.client.post(
            "/api/v1/inspections/create/", {"title": "缺素材巡检", "station_id": self.station.id}, format="json",
        )
        task_id = created.json()["id"]
        self.client.post(f"/api/v1/inspections/{task_id}/confirm/")
        self.client.post(f"/api/v1/inspections/{task_id}/start/")
        response = self.client.post(f"/api/v1/inspections/{task_id}/simulate/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            InspectionRecord.objects.filter(task_id=task_id, source=InspectionRecord.Source.TASK).count(), 1,
        )

# Create your tests here.
