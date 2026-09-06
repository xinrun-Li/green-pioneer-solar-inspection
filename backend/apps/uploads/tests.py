from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import ControlOperator
from apps.stations.models import Station

from .models import MediaAsset, UploadBatch

User = get_user_model()


class UploadApiTests(TestCase):
    def setUp(self):
        station = Station.objects.create(code="UPLOAD", name="上传测试电站")
        self.user = User.objects.create_user(username="uploader", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=self.user, display_name="上传员", station=station,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        self.client.force_login(self.user)

    def test_create_batch_and_upload_image(self):
        batch_response = self.client.post(
            "/api/v1/upload-batches/", {"region_note": "北区 A2"}, content_type="application/json"
        )
        self.assertEqual(batch_response.status_code, 201)
        image = SimpleUploadedFile("panel.jpg", b"\xff\xd8\xfffake-image-content", content_type="image/jpeg")
        response = self.client.post(
            f"/api/v1/upload-batches/{batch_response.json()['id']}/media", {"files": [image]}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UploadBatch.objects.count(), 1)
        self.assertEqual(MediaAsset.objects.get().kind, MediaAsset.Kind.IMAGE)

    def test_rejects_unsupported_file(self):
        batch = UploadBatch.objects.create(
            creator=self.user, station=self.user.operator_profile.station, region_note="北区"
        )
        upload = SimpleUploadedFile("notes.txt", b"not media", content_type="text/plain")
        response = self.client.post(f"/api/v1/upload-batches/{batch.id}/media", {"files": [upload]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "unsupported_media")

    def test_rejects_more_than_thirty_images(self):
        batch = UploadBatch.objects.create(
            creator=self.user, station=self.user.operator_profile.station, region_note="北区"
        )
        files = [
            SimpleUploadedFile(f"panel-{index}.jpg", b"\xff\xd8\xfffake", content_type="image/jpeg")
            for index in range(31)
        ]
        response = self.client.post(f"/api/v1/upload-batches/{batch.id}/media", {"files": files})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "too_many_images")

    def test_rejects_duplicate_file_in_same_batch(self):
        batch = UploadBatch.objects.create(
            creator=self.user, station=self.user.operator_profile.station, region_note="北区"
        )
        first = SimpleUploadedFile("panel.jpg", b"\xff\xd8\xffsame", content_type="image/jpeg")
        self.assertEqual(self.client.post(f"/api/v1/upload-batches/{batch.id}/media", {"files": [first]}).status_code, 201)
        second = SimpleUploadedFile("copy.jpg", b"\xff\xd8\xffsame", content_type="image/jpeg")
        response = self.client.post(f"/api/v1/upload-batches/{batch.id}/media", {"files": [second]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "duplicate_media")
