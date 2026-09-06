from django.urls import path

from .views import (
    approve_operator_view,
    audit_log_list_view,
    disable_operator_view,
    operator_detail_view,
    operator_list_view,
    reject_operator_view,
    reset_password_view,
    restore_operator_view,
)

urlpatterns = [
    path("operators/", operator_list_view, name="operator-list"),
    path("operators/<int:operator_id>/", operator_detail_view, name="operator-detail"),
    path("operators/<int:operator_id>/approve/", approve_operator_view, name="operator-approve"),
    path("operators/<int:operator_id>/reject/", reject_operator_view, name="operator-reject"),
    path("operators/<int:operator_id>/disable/", disable_operator_view, name="operator-disable"),
    path("operators/<int:operator_id>/restore/", restore_operator_view, name="operator-restore"),
    path("operators/<int:operator_id>/reset-password/", reset_password_view, name="operator-reset-password"),
    path("audit-logs/", audit_log_list_view, name="audit-log-list"),
]
