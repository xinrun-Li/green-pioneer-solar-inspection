from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import ControlOperator

User = get_user_model()


class DatasetApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dataset-user", password="ValidPass_2026!")
        ControlOperator.objects.create(user=self.user, display_name="数据员", review_status="approved")
        self.client.force_login(self.user)

    def upload_asset(self):
        response = self.client.post(
            "/api/v1/dataset-assets/",
            {"file": SimpleUploadedFile("sample.jpg", b"\xff\xd8\xffdataset", content_type="image/jpeg")},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_upload_requires_annotation_before_dataset_version(self):
        asset_id = self.upload_asset()
        response = self.client.post(
            "/api/v1/dataset-versions/",
            {"name": "v1", "version": "v1", "asset_ids": [asset_id]}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_annotate_submit_and_freeze_version(self):
        asset_id = self.upload_asset()
        annotation = self.client.post(
            f"/api/v1/dataset-assets/{asset_id}/annotations/",
            {"class_name": "normal", "bbox": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
            content_type="application/json",
        )
        self.assertEqual(annotation.status_code, 201)
        self.assertEqual(self.client.post(f"/api/v1/dataset-assets/{asset_id}/submit/").status_code, 200)
        version = self.client.post(
            "/api/v1/dataset-versions/",
            {"name": "演示集", "version": "v1", "asset_ids": [asset_id]}, content_type="application/json",
        )
        self.assertEqual(version.status_code, 201)
        frozen = self.client.post(f"/api/v1/dataset-versions/{version.json()['id']}/freeze/")
        self.assertEqual(frozen.status_code, 200)
        self.assertEqual(frozen.json()["status"], "frozen")
