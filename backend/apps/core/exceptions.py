from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def _first_message(value):
    if isinstance(value, dict):
        return _first_message(next(iter(value.values()), "请求参数不正确"))
    if isinstance(value, list):
        return _first_message(value[0] if value else "请求参数不正确")
    return str(value)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        errors = response.data
        response.data = {
            "code": "validation_error",
            "message": _first_message(errors),
            "errors": errors,
        }
    elif isinstance(response.data, dict) and "detail" in response.data:
        response.data = {
            "code": getattr(exc, "default_code", "request_failed"),
            "message": str(response.data["detail"]),
        }
    return response

