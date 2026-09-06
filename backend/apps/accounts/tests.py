import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stations.models import Station

from .models import AccountNotification, AuditLog, ControlOperator

User = get_user_model()


class AccountApiTests(TestCase):
    def setUp(self):
        self.station = Station.objects.create(code="TEST", name="测试电站")

    def test_register_creates_pending_operator(self):
        response = self.client.post("/api/v1/auth/register", {
            "username": "new_operator", "display_name": "新控制员",
            "phone": "13800000000",
            "password": "ValidPass_2026!", "password_confirm": "ValidPass_2026!",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        profile = ControlOperator.objects.get(user__username="new_operator")
        self.assertEqual(profile.review_status, ControlOperator.ReviewStatus.PENDING)
        self.assertEqual(profile.role, ControlOperator.Role.INSPECTOR)
        self.assertEqual(profile.phone, "13800000000")

    def test_registered_user_cannot_login_or_access_business_api_before_review(self):
        user = User.objects.create_user(username="operator", password="ValidPass_2026!")
        profile = ControlOperator.objects.create(user=user, display_name="控制员", station=self.station)
        pending = self.client.post("/api/v1/auth/login", {
            "username": "operator", "password": "ValidPass_2026!", "remember": False,
        }, content_type="application/json")
        self.assertEqual(pending.status_code, 403)
        self.assertEqual(pending.json()["code"], "registration_pending")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/v1/inspections/").status_code, 403)

        profile.review_status = ControlOperator.ReviewStatus.APPROVED
        profile.save(update_fields=("review_status",))
        approved = self.client.post("/api/v1/auth/login", {
            "username": "operator", "password": "ValidPass_2026!", "remember": True,
        }, content_type="application/json")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["user"]["station"]["name"], "测试电站")

    def test_rejected_user_cannot_login(self):
        user = User.objects.create_user(username="rejected", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=user, display_name="被拒绝用户", review_status=ControlOperator.ReviewStatus.REJECTED,
            rejection_reason="资料不完整",
        )
        response = self.client.post(
            "/api/v1/auth/login", {"username": "rejected", "password": "ValidPass_2026!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "registration_rejected")


class OperatorManagementApiTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="manager", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=self.manager, display_name="审核管理员", role=ControlOperator.Role.ADMIN,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        self.pending_user = User.objects.create_user(username="pending", password="ValidPass_2026!")
        self.pending = ControlOperator.objects.create(
            user=self.pending_user, display_name="待审核用户", phone="13900000000",
        )
        self.client.force_login(self.manager)

    def test_operator_list_filters_and_puts_pending_first(self):
        approved_user = User.objects.create_user(username="approved", password="ValidPass_2026!")
        ControlOperator.objects.create(
            user=approved_user, display_name="已通过用户", role=ControlOperator.Role.VIEWER,
            review_status=ControlOperator.ReviewStatus.APPROVED,
        )
        response = self.client.get("/api/v1/accounts/operators/?role=inspector&search=待审核")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["status"], "pending")

    def test_approve_reject_disable_restore_and_audit(self):
        response = self.client.post(
            f"/api/v1/accounts/operators/{self.pending.pk}/approve/",
            {"role": "reviewer", "reason": "审核资料完整"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.role, ControlOperator.Role.REVIEWER)
        self.assertEqual(self.pending.review_status, ControlOperator.ReviewStatus.APPROVED)
        self.assertEqual(AuditLog.objects.filter(action_type=AuditLog.ActionType.APPROVE).count(), 1)
        notification = AccountNotification.objects.get(user=self.pending_user)
        self.assertEqual(notification.kind, AccountNotification.Kind.APPROVED)
        self.client.force_login(self.pending_user)
        notifications = self.client.get("/api/v1/auth/notifications")
        self.assertEqual(notifications.status_code, 200)
        self.assertEqual(notifications.json()["unread_count"], 1)
        self.client.force_login(self.manager)

        rejected_user = User.objects.create_user(username="reject-me", password="ValidPass_2026!")
        rejected = ControlOperator.objects.create(user=rejected_user, display_name="待补充")
        response = self.client.post(
            f"/api/v1/accounts/operators/{rejected.pk}/reject/", {"reason": "手机号无法核验"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        rejected.refresh_from_db()
        self.assertEqual(rejected.rejection_reason, "手机号无法核验")
        self.assertEqual(AccountNotification.objects.get(user=rejected_user).kind, AccountNotification.Kind.REJECTED)
        rejected_login = self.client.post(
            "/api/v1/auth/login", {"username": "reject-me", "password": "ValidPass_2026!"}, format="json",
        )
        self.assertEqual(rejected_login.status_code, 403)
        self.assertEqual(rejected_login.json()["code"], "registration_rejected")

        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(f"/api/v1/accounts/operators/{self.pending.pk}/disable/", {"reason": "离岗"}, format="json").status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.review_status, ControlOperator.ReviewStatus.DISABLED)
        self.assertFalse(self.pending.user.is_active)
        self.assertEqual(self.client.post(f"/api/v1/accounts/operators/{self.pending.pk}/restore/", format="json").status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.review_status, ControlOperator.ReviewStatus.APPROVED)
        self.assertTrue(self.pending.user.is_active)

    def test_edit_reset_password_audit_log_filters_and_superuser_delete(self):
        response = self.client.patch(
            f"/api/v1/accounts/operators/{self.pending.pk}/",
            data=json.dumps({"display_name": "新姓名", "phone": "13700000000", "role": "viewer", "reason": "岗位调整"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.display_name, "新姓名")
        self.assertEqual(self.pending.role, ControlOperator.Role.VIEWER)
        self.assertEqual(AuditLog.objects.filter(action_type=AuditLog.ActionType.ROLE_CHANGE).count(), 1)
        response = self.client.post(
            f"/api/v1/accounts/operators/{self.pending.pk}/reset-password/",
            {"password": "NewValidPass_2026!", "password_confirm": "NewValidPass_2026!"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.user.refresh_from_db()
        self.assertTrue(self.pending.user.check_password("NewValidPass_2026!"))
        generated = self.client.post(
            f"/api/v1/accounts/operators/{self.pending.pk}/reset-password/",
            content_type="application/json",
        )
        self.assertEqual(generated.status_code, 200)
        temporary_password = generated.json()["temporary_password"]
        self.pending.user.refresh_from_db()
        self.assertTrue(self.pending.user.check_password(temporary_password))
        response = self.client.get("/api/v1/accounts/audit-logs/?action_type=role_change")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["action_label"], "角色变更")
        response = self.client.get("/api/v1/accounts/audit-logs/?search=审核管理员")
        self.assertGreaterEqual(response.json()["count"], 1)

        target = User.objects.create_user(username="delete-me", password="ValidPass_2026!")
        target_profile = ControlOperator.objects.create(user=target, display_name="删除用户")
        self.assertEqual(self.client.delete(
            f"/api/v1/accounts/operators/{target_profile.pk}/",
            data=json.dumps({"reason": "账号清理"}), content_type="application/json",
        ).status_code, 403)
        self.manager.is_superuser = True
        self.manager.save(update_fields=("is_superuser",))
        self.assertEqual(self.client.delete(
            f"/api/v1/accounts/operators/{target_profile.pk}/",
            data=json.dumps({"reason": "账号清理"}), content_type="application/json",
        ).status_code, 204)
        self.assertFalse(User.objects.filter(pk=target.pk).exists())

    def test_rejected_registration_can_be_submitted_again(self):
        self.pending.review_status = ControlOperator.ReviewStatus.REJECTED
        self.pending.rejection_reason = "请补充手机号"
        self.pending.save(update_fields=("review_status", "rejection_reason"))
        response = self.client.post(
            "/api/v1/auth/register",
            {
                "username": "pending", "display_name": "重新提交", "phone": "13600000000",
                "password": "AnotherValidPass_2026!", "password_confirm": "AnotherValidPass_2026!",
            }, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.review_status, ControlOperator.ReviewStatus.PENDING)
        self.assertEqual(self.pending.rejection_reason, "")
        self.assertEqual(self.pending.phone, "13600000000")
