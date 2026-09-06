from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from .deepseek import DeepSeekError, generate_deepseek_reply
from .services import IntentEngine
from apps.inspections.models import InspectionEvent, InspectionTask, Waypoint
from apps.stations.models import Panel, Region, SolarArray, Station


class IntentEngineTests(TestCase):
    def setUp(self):
        self.engine = IntentEngine()

    def test_query_anomaly(self):
        intent, _, confidence = self.engine.classify("查询北区异常")
        self.assertEqual(intent, "query_anomaly")
        self.assertGreater(confidence, 0.5)

    def test_query_task(self):
        intent, _, _ = self.engine.classify("任务进度")
        self.assertEqual(intent, "query_task")

    def test_query_stats(self):
        intent, _, _ = self.engine.classify("电站概况")
        self.assertEqual(intent, "query_stats")

    def test_create_task(self):
        intent, _, _ = self.engine.classify("创建新任务")
        self.assertEqual(intent, "create_task")

    def test_start_task(self):
        intent, slots, _ = self.engine.classify("开始任务 #3")
        self.assertEqual(intent, "start_task")
        self.assertEqual(slots.get("task_id"), "3")

    def test_pause_task(self):
        intent, _, _ = self.engine.classify("暂停任务")
        self.assertEqual(intent, "pause_task")

    def test_navigate(self):
        intent, _, _ = self.engine.classify("打开报告中心")
        self.assertEqual(intent, "navigate")

    def test_generate_report(self):
        intent, _, _ = self.engine.classify("生成本月报告")
        self.assertEqual(intent, "generate_report")

    def test_export_data(self):
        intent, _, _ = self.engine.classify("导出异常数据")
        self.assertEqual(intent, "export_data")

    def test_help(self):
        intent, _, _ = self.engine.classify("能做什么")
        self.assertEqual(intent, "help")

    def test_unknown_message_routes_to_cloud_chat(self):
        intent, slots, confidence = self.engine.classify("你好，介绍一下你自己")
        self.assertEqual(intent, "help")
        self.assertEqual(slots, {})
        self.assertEqual(confidence, 0.3)


class DeepSeekClientTests(SimpleTestCase):
    @override_settings(DEEPSEEK_API_KEY="")
    def test_missing_api_key_has_clear_error(self):
        with self.assertRaisesRegex(DeepSeekError, "DEEPSEEK_API_KEY"):
            generate_deepseek_reply(Mock(), "你好")

    @override_settings(
        DEEPSEEK_API_KEY="test-key",
        DEEPSEEK_BASE_URL="https://api.deepseek.com",
        DEEPSEEK_MODEL="deepseek-v4-flash",
        DEEPSEEK_TIMEOUT_SECONDS=45,
    )
    @patch("apps.assistant.deepseek._conversation_messages")
    @patch("apps.assistant.deepseek.requests.post")
    def test_chat_uses_v4_flash_non_thinking_mode(self, post, conversation_messages):
        conversation_messages.return_value = [{"role": "user", "content": "你好"}]
        post.return_value = Mock(
            ok=True,
            status_code=200,
            json=Mock(return_value={"choices": [{"message": {"content": "你好，我是绿能助手。"}}]}),
        )

        result = generate_deepseek_reply(Mock(), "你好")

        self.assertEqual(result, "你好，我是绿能助手。")
        request = post.call_args.kwargs
        self.assertEqual(request["json"]["model"], "deepseek-v4-flash")
        self.assertEqual(request["json"]["thinking"], {"type": "disabled"})
        self.assertNotIn("test-key", str(request["json"]))

    @override_settings(
        DEEPSEEK_API_KEY="test-key",
        DEEPSEEK_BASE_URL="https://api.deepseek.com",
        DEEPSEEK_MODEL="deepseek-v4-flash",
        DEEPSEEK_TIMEOUT_SECONDS=45,
    )
    @patch("apps.assistant.deepseek._conversation_messages", return_value=[])
    @patch("apps.assistant.deepseek.requests.post")
    def test_authentication_error_is_user_friendly(self, post, _conversation_messages):
        post.return_value = Mock(
            ok=False,
            status_code=401,
            json=Mock(return_value={"error": {"message": "invalid key"}}),
        )
        with self.assertRaisesRegex(DeepSeekError, "API Key 无效"):
            generate_deepseek_reply(Mock(), "你好")


class AssistantAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="assistant-test",
            email="assistant@example.com",
            password="test-password",
        )
        self.client.force_authenticate(self.user)

    @override_settings(DEEPSEEK_API_KEY="test-key", DEEPSEEK_MODEL="deepseek-v4-flash")
    def test_status_does_not_expose_api_key(self):
        response = self.client.get("/api/v1/assistant/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "DeepSeek")
        self.assertEqual(response.data["model"], "deepseek-v4-flash")
        self.assertTrue(response.data["configured"])
        self.assertNotContains(response, "test-key")

    @override_settings(DEEPSEEK_API_KEY="test-key", DEEPSEEK_MODEL="deepseek-v4-flash")
    @patch("apps.assistant.views.generate_deepseek_reply", return_value="你好，我是绿能助手。")
    def test_plain_conversation_returns_deepseek_response(self, generate_reply):
        response = self.client.post(
            "/api/v1/assistant/query/",
            {"message": "你好，请介绍一下你自己"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["response"], "你好，我是绿能助手。")
        self.assertEqual(response.data["intent"], "chat")
        self.assertEqual(response.data["intent_display"], "智能对话")
        self.assertEqual(response.data["source"], "cloud")
        self.assertEqual(response.data["status"], "pending")
        generate_reply.assert_called_once_with(self.user, "你好，请介绍一下你自己")

    def test_read_only_query_returns_result_without_confirmation_step(self):
        response = self.client.post(
            "/api/v1/assistant/query/",
            {"message": "查询北区异常"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.assertIsNone(response.data["draft_action"])

    def test_retry_read_only_query_returns_result_without_confirmation_step(self):
        response = self.client.post(
            "/api/v1/assistant/query/",
            {"message": "查询北区异常"},
            format="json",
        )
        conversation = response.data
        conversation["status"] = "drafted"
        conversation["draft_action"] = {
            "action_type": "query",
            "target": "异常事件",
            "payload": {},
        }
        from apps.assistant.models import AgentConversation
        AgentConversation.objects.filter(pk=conversation["id"]).update(
            status="drafted", draft_action=conversation["draft_action"]
        )

        retried = self.client.post(
            "/api/v1/assistant/confirm/",
            {"conversation_id": conversation["id"], "action": "retry"},
            format="json",
        )
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.data["conversation"]["status"], "pending")
        self.assertIsNone(retried.data["conversation"]["draft_action"])

    def test_confirm_create_task_really_creates_task_and_route(self):
        station = Station.objects.create(code="ASSIST", name="助手测试电站")
        region = Region.objects.create(station=station, name="北区", direction="north", sort_order=1)
        array = SolarArray.objects.create(region=region, code="A1", rows=1, columns=1)
        Panel.objects.create(array=array, full_code="A1-R01-C01", short_code="A1-001", row=1, column=1)
        response = self.client.post("/api/v1/assistant/query/", {"message": "创建北区巡检任务"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "drafted")
        confirmed = self.client.post(
            "/api/v1/assistant/confirm/",
            {"conversation_id": response.data["id"], "action": "confirm"}, format="json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.data["success"], confirmed.data)
        task = InspectionTask.objects.latest("id")
        self.assertIn("已创建", confirmed.data["conversation"]["response"])
        self.assertEqual(task.status, InspectionTask.Status.DRAFT)
        self.assertEqual(task.waypoints.count(), 1)
        self.assertEqual(task.events.filter(event_type=InspectionEvent.EventType.CREATED).count(), 1)

    def test_confirm_generate_report_creates_ready_report(self):
        station = Station.objects.create(code="REPORT-ASSIST", name="报告助手测试电站")
        task = InspectionTask.objects.create(
            title="待分析巡检结果", station=station, status=InspectionTask.Status.COMPLETED, created_by=self.user,
        )
        response = self.client.post(
            "/api/v1/assistant/query/", {"message": f"生成任务 #{task.id} 的 PDF 分析报告"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        confirmed = self.client.post(
            "/api/v1/assistant/confirm/",
            {"conversation_id": response.data["id"], "action": "confirm"}, format="json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.data["success"])
        self.assertEqual(confirmed.data["conversation"]["status"], "confirmed")
