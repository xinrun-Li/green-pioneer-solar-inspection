from rest_framework.permissions import BasePermission


class IsApprovedOperator(BasePermission):
    message = "账户未审核通过、未登录或已停用"

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, "operator_profile", None)
        return bool(
            profile
            and profile.review_status == profile.ReviewStatus.APPROVED
            and request.user.is_active
        )


class IsAccountManager(BasePermission):
    message = "当前账户没有控制人员管理权限"

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "operator_profile", None)
        return bool(request.user.is_superuser or request.user.is_staff or (
            profile and profile.has_account_management_permission
        ))
