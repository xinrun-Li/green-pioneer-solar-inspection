from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import ControlOperator
from apps.stations.models import Station
from apps.uploads.models import MediaAsset, UploadBatch

from .models import Detection, RecognitionJob, ReviewAction
from .services import YOLO_CLASS_MAP

User = get_user_model()


class MockRecognitionApiTests(TestCase):
    def setUp(self):
        station = Station.objects.create(code="RECOG", name="识别测试电站")
        self.user = User.objects.create_user(username="recognizer", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=self.user, display_name="识别员", station=station,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        self.batch = UploadBatch.objects.create(creator=self.user, station=station, region_note="北区 A2")
        upload = SimpleUploadedFile("panel.jpg", b"deterministic-image", content_type="image/jpeg")
        self.media = MediaAsset.objects.create(
            batch=self.batch, kind=MediaAsset.Kind.IMAGE, original_file=upload,
            original_name="panel.jpg", mime_type="image/jpeg", size_bytes=19, checksum="a" * 64,
        )
        self.client.force_login(self.user)

    def test_mock_job_produces_deterministic_three_class_results(self):
        created = self.client.post(
            "/api/v1/recognition-jobs/", {"media_id": self.media.id}, content_type="application/json"
        )
        self.assertEqual(created.status_code, 201)
        response = self.client.post(f"/api/v1/recognition-jobs/{created.json()['id']}/run-mock")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_demo_data"])
        self.assertEqual(response.json()["progress"], 100)
        self.assertEqual(len(response.json()["detections"]), 6)

    def test_pending_detection_can_be_reviewed_with_audit_record(self):
        job = RecognitionJob.objects.create(media=self.media, status=RecognitionJob.Status.REVIEW, progress=100)
        detection = Detection.objects.create(
            job=job, sequence=1, x=.1, y=.1, width=.2, height=.2,
            original_class=Detection.DetectionClass.CLEANING, confidence=.68,
            review_status=Detection.ReviewStatus.PENDING,
        )
        response = self.client.post(
            f"/api/v1/detections/{detection.id}/review",
            {"confirmed_class": "repair", "note": "人工确认"}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["effective_class"], "repair")
        self.assertEqual(ReviewAction.objects.get().previous_class, "cleaning")
        job.refresh_from_db()
        self.assertEqual(job.status, RecognitionJob.Status.COMPLETED)

    def test_yolo_classes_map_to_existing_business_classes(self):
        self.assertEqual(YOLO_CLASS_MAP["Clean"], "normal")
        self.assertEqual(YOLO_CLASS_MAP["Dust"], "cleaning")
        self.assertEqual(YOLO_CLASS_MAP["Electrical"], "repair")

    def test_generic_run_endpoint_keeps_mock_compatibility(self):
        created = self.client.post(
            "/api/v1/recognition-jobs/", {"media_id": self.media.id}, content_type="application/json"
        )
        response = self.client.post(f"/api/v1/recognition-jobs/{created.json()['id']}/run/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["adapter"], "mock")
        self.assertTrue(response.json()["is_demo_data"])
