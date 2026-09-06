from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import ControlOperator
from apps.datasets.models import DatasetVersion

from .models import ModelVersion

User = get_user_model()


class TrainingApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="trainer", password="ValidPass_2026!")
        ControlOperator.objects.create(user=self.user, display_name="训练员", review_status="approved")
        self.client.force_login(self.user)

    def test_model_collection_exposes_mock_version(self):
        response = self.client.get("/api/v1/model-versions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["version"], "mock-v1")

    def test_training_requires_frozen_dataset(self):
        dataset = DatasetVersion.objects.create(name="草稿", version="draft-v1", created_by=self.user)
        response = self.client.post("/api/v1/training-runs/", {"dataset_version_id": dataset.id}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_candidate_model_can_be_activated(self):
        active = ModelVersion.objects.create(
            name="演示", version="mock-v1", model_type="mock", status="active", is_active=True, created_by=self.user,
        )
        candidate = ModelVersion.objects.create(
            name="候选", version="yolo-v1", model_type="yolo", status="candidate", created_by=self.user,
        )
        response = self.client.post(f"/api/v1/model-versions/{candidate.id}/activate/")
        self.assertEqual(response.status_code, 200)
        candidate.refresh_from_db()
        active.refresh_from_db()
        self.assertTrue(candidate.is_active)
        self.assertFalse(active.is_active)

    def test_frozen_dataset_creates_completed_offline_training_result(self):
        dataset = DatasetVersion.objects.create(
            name="冻结集", version="frozen-v1", created_by=self.user,
            status=DatasetVersion.Status.FROZEN,
        )
        response = self.client.post(
            "/api/v1/training-runs/", {"dataset_version_id": dataset.id}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["progress"], 100)
        self.assertTrue(response.json()["output_model_version_id"])
