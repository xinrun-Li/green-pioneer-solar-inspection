"""DeepSeek 云端对话客户端。"""

from __future__ import annotations

from typing import Any

import requests
from django.conf import settings

from .models import AgentConversation

SYSTEM_PROMPT = """你是“绿能助手”，服务于光伏电站巡检系统。
请使用简洁、专业、自然的中文回答。
你可以解释光伏组件、积雪、污渍、故障、清洗和维修相关常识，也可以进行普通对话。
不要声称已经查询、修改或创建了系统中的真实数据；真实巡检数据和业务操作由系统本地接口处理。
当信息不足时明确说明，并建议用户提供必要信息。不要编造检测结果、设备编号或任务状态。"""


class DeepSeekError(RuntimeError):
    """可安全展示给前端的 DeepSeek 调用错误。"""


def is_deepseek_configured() -> bool:
    return bool(settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_MODEL)


def _conversation_messages(user, message: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = AgentConversation.objects.filter(
        user=user,
        error_message="",
    ).exclude(response="").order_by("-created_at")[: settings.DEEPSEEK_MAX_HISTORY]

    for item in reversed(list(history)):
        messages.append({"role": "user", "content": item.message})
        messages.append({"role": "assistant", "content": item.response})
    messages.append({"role": "user", "content": message})
    return messages


def _error_message(status_code: int, payload: Any) -> str:
    known = {
        400: "DeepSeek 请求参数不正确，请联系管理员检查模型配置。",
        401: "DeepSeek API Key 无效，请检查服务端配置。",
        402: "DeepSeek API 余额不足，请充值后重试。",
        422: "DeepSeek 请求参数不受支持，请检查模型配置。",
        429: "DeepSeek 请求过于频繁，请稍后再试。",
        500: "DeepSeek 服务暂时异常，请稍后再试。",
        503: "DeepSeek 服务当前繁忙，请稍后再试。",
    }
    if status_code in known:
        return known[status_code]
    detail = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message", ""))
        elif error:
            detail = str(error)
    return f"DeepSeek 请求失败（HTTP {status_code}）" + (f"：{detail[:160]}" if detail else "。")


def generate_deepseek_reply(user, message: str) -> str:
    """调用 DeepSeek V4 非思考模式生成普通对话回复。"""
    if not is_deepseek_configured():
        raise DeepSeekError("DeepSeek 尚未配置，请先在服务端 .env 中填写 DEEPSEEK_API_KEY。")

    try:
        response = requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.DEEPSEEK_MODEL,
                "messages": _conversation_messages(user, message),
                "stream": False,
                "max_tokens": 800,
                "thinking": {"type": "disabled"},
            },
            timeout=(8, settings.DEEPSEEK_TIMEOUT_SECONDS),
        )
    except requests.Timeout as exc:
        raise DeepSeekError("DeepSeek 响应超时，请稍后重试。") from exc
    except requests.RequestException as exc:
        raise DeepSeekError("无法连接 DeepSeek 服务，请检查服务器网络后重试。") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise DeepSeekError(f"DeepSeek 返回了无法解析的数据（HTTP {response.status_code}）。") from exc

    if not response.ok:
        raise DeepSeekError(_error_message(response.status_code, payload))

    try:
        content = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise DeepSeekError("DeepSeek 返回内容为空，请重新提问。") from exc
    if not content:
        raise DeepSeekError("DeepSeek 返回内容为空，请重新提问。")
    return content
