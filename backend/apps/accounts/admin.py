from django.contrib import admin
from django.utils.timezone import now

from .models import AccountNotification, AuditLog, ControlOperator


@admin.register(ControlOperator)
class ControlOperatorAdmin(admin.ModelAdmin):
    list_display = ("display_name", "username", "phone", "role", "review_status", "station", "created_at")
    list_filter = ("review_status", "role", "station")
    search_fields = ("display_name", "phone", "user__username")
    autocomplete_fields = ("user", "reviewed_by")
    actions = ("approve_accounts", "reject_accounts", "disable_accounts")

    @admin.display(description="账号", ordering="user__username")
    def username(self, obj):
        return obj.user.username

    def _review(self, request, queryset, review_status):
        queryset.update(review_status=review_status, reviewed_by=request.user, reviewed_at=now())

    @admin.action(description="审核通过所选账户")
    def approve_accounts(self, request, queryset):
        ready = queryset.exclude(station=None)
        self._review(request, ready, ControlOperator.ReviewStatus.APPROVED)
        skipped = queryset.filter(station=None).count()
        if skipped:
            self.message_user(request, f"{skipped} 个账户尚未分配电站，未执行审核通过", level="WARNING")

    @admin.action(description="拒绝所选账户")
    def reject_accounts(self, request, queryset):
        self._review(request, queryset, ControlOperator.ReviewStatus.REJECTED)

    @admin.action(description="停用所选账户")
    def disable_accounts(self, request, queryset):
        self._review(request, queryset, ControlOperator.ReviewStatus.DISABLED)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "operator", "action_type", "target_user", "reason")
    list_filter = ("action_type", "created_at")
    search_fields = ("operator__username", "target_user__username", "reason")
    readonly_fields = ("operator", "action_type", "target_user", "reason", "created_at")


@admin.register(AccountNotification)
class AccountNotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "title", "is_read")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("user__username", "title", "content")
    readonly_fields = ("user", "kind", "title", "content", "created_at")
