from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import ControlOperator

from .models import Panel, PanelStatusHistory, SolarArray, Station

User = get_user_model()


class DemoStationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.station = Station.objects.get(code="DEMO-001")
        cls.user = User.objects.create_user(username="map_operator", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=cls.user, display_name="地图控制员", station=cls.station,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )

    def test_seed_creates_expected_structure_and_is_idempotent(self):
        self.assertEqual(self.station.regions.count(), 4)
        self.assertEqual(SolarArray.objects.filter(region__station=self.station).count(), 12)
        self.assertEqual(Panel.objects.filter(array__region__station=self.station).count(), 240)
        self.assertEqual(PanelStatusHistory.objects.filter(panel__array__region__station=self.station).count(), 7200)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Panel.objects.filter(array__region__station=self.station).count(), 240)
        self.assertEqual(PanelStatusHistory.objects.filter(panel__array__region__station=self.station).count(), 7200)

    def test_map_api_returns_all_panels_for_approved_operator(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/stations/current/map")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["panel_count"], 240)
        self.assertEqual(len(payload["regions"]), 4)
        self.assertEqual(sum(len(region["arrays"]) for region in payload["regions"]), 12)

    def test_map_api_rejects_anonymous_user(self):
        response = self.client.get("/api/v1/stations/current/map")
        self.assertEqual(response.status_code, 403)

