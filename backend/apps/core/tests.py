from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_endpoint_responds(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "green-pioneer-api")
        self.assertIn(response.json()["status"], {"ok", "degraded"})

