"""智能助手意图引擎：10 类意图规则引擎 + 槽位提取 + 草稿生成 + 云端回退"""

import re
from datetime import datetime

from apps.events.models import AbnormalEvent
from apps.inspections.models import InspectionTask
from apps.stations.models import Panel, Station

# ─── 意图定义 ────────────────────────────────────────────────────────────────

INTENT_DEFINITIONS = {
    "query_anomaly": {
        "label": "查询异常",
        "keywords": ["异常", "故障", "清洗", "维修", "告警", "问题", "不正常"],
        "slots": ["panel_code", "region", "station", "event_type"],
    },
    "query_task": {
        "label": "查询任务",
        "keywords": ["任务", "巡检", "进度", "航点", "路线"],
        "slots": ["task_id", "task_title", "station"],
    },
    "query_stats": {
        "label": "查询统计",
        "keywords": ["统计", "概况", "汇总", "总计", "总览", "概览", "数据"],
        "slots": ["station", "period"],
    },
    "create_task": {
        "label": "创建任务",
        "keywords": ["创建任务", "新建任务", "新任务", "安排巡检", "开始巡检", "创建巡检", "创建"],
        "slots": ["station", "title", "region", "array_code"],
    },
    "start_task": {
        "label": "开始任务",
        "keywords": ["开始任务", "启动任务", "执行任务", "开始巡检", "启动巡检"],
        "slots": ["task_id", "task_title"],
    },
    "pause_task": {
        "label": "暂停任务",
        "keywords": ["暂停", "停止", "中断", "暂停任务"],
        "slots": ["task_id", "task_title"],
    },
    "navigate": {
        "label": "跳转页面",
        "keywords": ["打开", "跳转", "前往", "进入", "去", "查看"],
        "slots": ["page", "target"],
    },
    "generate_report": {
        "label": "生成报告",
        "keywords": ["报告", "报表", "导出报告", "生成报告", "分析报告", "汇报"],
        "slots": ["station", "period", "format", "task_id"],
    },
    "export_data": {
        "label": "导出数据",
        "keywords": ["导出异常", "导出数据", "导出", "下载", "备份"],
        "slots": ["target", "format"],
    },
    "help": {
        "label": "帮助",
        "keywords": ["帮助", "说明", "怎么用", "功能", "支持", "能做什么", "help"],
        "slots": [],
    },
}

# ─── 页面别名映射 ─────────────────────────────────────────────────────────────

PAGE_ALIASES = {
    "首页": "dashboard", "控制台": "dashboard", "dashboard": "dashboard",
    "电站": "stations", "地图": "stations", "电站地图": "stations",
    "上传": "upload", "识别": "recognition", "上传识别": "recognition",
    "任务": "tasks", "任务中心": "tasks", "巡检任务": "tasks",
    "助手": "assistant", "智能助手": "assistant",
    "报告": "reports", "报告中心": "reports",
    "历史": "history", "历史数据": "history",
    "设置": "settings", "系统设置": "settings",
}

# ─── 槽位提取规则 ─────────────────────────────────────────────────────────────

SLOT_PATTERNS = {
    "panel_code": re.compile(r"(?P<value>[A-Z]\d{1,3}[A-Z]\d{1,3})"),
    "task_id": re.compile(r"(?:任务|ID|编号)\s*[#第]?\s*(\d+)", re.IGNORECASE),
    "task_title": re.compile(r"(?:任务[：:])?(?P<value>.{2,20}任务)"),
    "station": re.compile(r"(?P<value>[1-9]\d*号?电站|示范电站|实验电站)"),
    "region": re.compile(r"(?P<value>[东南西北][区])"),
    "event_type": re.compile(r"(清洗|维修|异常|故障)"),
    "period": re.compile(r"(?P<value>今天|昨天|本周|本月|近7天|近30天|全部)"),
    "page": re.compile(r"(?P<value>.+)"),
    "target": re.compile(r"(?P<value>.+)"),
    "format": re.compile(r"(?P<value>网页|Excel|PDF|全部)"),
    "array_code": re.compile(r"(?P<value>[A-Z]\d+)"),
}


class IntentEngine:
    """意图引擎：规则匹配 + 槽位提取"""

    def classify(self, message: str) -> tuple[str, dict, float]:
        """返回 (intent, slots, confidence)"""
        clean = message.strip()

        # 中文自然表达经常在“创建”和“巡检任务”之间插入区域名，
        # 例如“创建北区巡检任务”；此时创建动作优先于普通任务查询。
        if "创建" in clean and ("巡检" in clean or "任务" in clean):
            definition = INTENT_DEFINITIONS["create_task"]
            return "create_task", self._extract_slots(clean, definition["slots"]), 0.9

        matches = []
        for intent, definition in INTENT_DEFINITIONS.items():
            score = self._match_keywords(clean, definition["keywords"])
            if score > 0:
                matches.append((score, intent, definition))
        if matches:
            score, intent, definition = max(matches, key=lambda item: item[0])
            slots = self._extract_slots(clean, definition["slots"])
            confidence = min(0.5 + 0.1 * score, 0.95)
            return intent, slots, confidence

        return "help", {}, 0.3

    def _match_keywords(self, message: str, keywords: list[str]) -> int:
        score = 0
        for kw in keywords:
            if kw in message:
                score += len(kw)
        return score

    def _extract_slots(self, message: str, expected_slots: list[str]) -> dict:
        slots = {}
        for slot_name in expected_slots:
            pattern = SLOT_PATTERNS.get(slot_name)
            if pattern:
                match = pattern.search(message)
                if match:
                    slots[slot_name] = match.group("value") if "value" in pattern.groupindex else match.group(1)
        return slots

    def render_page(self, page_alias: str) -> str:
        return PAGE_ALIASES.get(page_alias, page_alias)


# ─── 草稿生成 ─────────────────────────────────────────────────────────────────

def generate_draft(intent: str, slots: dict, user) -> dict:
    """根据意图和槽位生成草稿动作"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if intent == "query_anomaly":
        filters = {}
        if slots.get("panel_code"):
            filters["panel__full_code__icontains"] = slots["panel_code"]
        if slots.get("station"):
            filters["panel__array__region__station__name__icontains"] = slots["station"]
        if slots.get("event_type"):
            et = {"清洗": "cleaning", "维修": "repair"}.get(slots["event_type"], "")
            if et:
                filters["event_type"] = et
        count = AbnormalEvent.objects.filter(**filters).count() if filters else AbnormalEvent.objects.count()
        return {
            "action_type": "query",
            "target": "异常事件",
            "payload": {
                "summary": f"共 {count} 条异常事件",
                "filters": filters,
                "timestamp": now,
            },
            "response": f"当前共 {count} 条异常事件待处理。",
        }

    if intent == "query_task":
        filters = {}
        if slots.get("task_id"):
            filters["pk"] = int(slots["task_id"])
        elif slots.get("task_title"):
            filters["title__icontains"] = slots["task_title"]
        elif slots.get("station"):
            filters["station__name__icontains"] = slots["station"]
        tasks = InspectionTask.objects.filter(**filters) if filters else InspectionTask.objects.all()
        count = tasks.count()
        running = tasks.filter(status="running").count()
        completed = tasks.filter(status="completed").count()
        return {
            "action_type": "query",
            "target": "巡检任务",
            "payload": {
                "summary": f"共 {count} 个任务（执行中 {running}，已完成 {completed}）",
                "filters": filters,
                "timestamp": now,
            },
            "response": f"共 {count} 个巡检任务，其中执行中 {running} 个，已完成 {completed} 个。",
        }

    if intent == "query_stats":
        station_count = Station.objects.filter(is_active=True).count()
        panel_count = Panel.objects.filter(is_active=True).count() if hasattr(Panel, "is_active") else Panel.objects.count()
        open_events = AbnormalEvent.objects.filter(status="open").count()
        return {
            "action_type": "query",
            "target": "电站统计",
            "payload": {
                "stations": station_count,
                "panels": panel_count,
                "open_events": open_events,
                "timestamp": now,
            },
            "response": f"共 {station_count} 个电站，{panel_count} 块组件，{open_events} 个异常事件待处理。",
        }

    if intent == "create_task":
        station_name = slots.get("station", "1号电站")
        title = slots.get("title", f"{station_name}巡检任务")
        try:
            station = Station.objects.get(name__icontains=station_name)
        except Station.DoesNotExist:
            station = Station.objects.first()
        return {
            "action_type": "create",
            "target": "巡检任务",
            "payload": {
                "title": title,
                "station_id": station.pk if station else None,
                "station_name": station.name if station else station_name,
                "region": slots.get("region", ""),
                "array_code": slots.get("array_code", ""),
                "timestamp": now,
            },
            "response": f"准备创建巡检任务「{title}」，目标电站：{station.name if station else station_name}。请确认执行。",
        }

    if intent == "start_task":
        task_id = slots.get("task_id")
        if task_id:
            try:
                task = InspectionTask.objects.get(pk=int(task_id))
                return {
                    "action_type": "update",
                    "target": f"巡检任务 #{task.pk}",
                    "payload": {
                        "task_id": task.pk,
                        "action": "start",
                        "current_status": task.status,
                        "title": task.title,
                        "timestamp": now,
                    },
                    "response": f"准备启动任务「{task.title}」（当前状态：{task.get_status_display()}）。请确认执行。",
                }
            except (InspectionTask.DoesNotExist, ValueError):
                pass
        return {
            "action_type": "query",
            "target": "巡检任务",
            "payload": {"action": "start", "timestamp": now},
            "response": "请指定要启动的任务 ID（如：开始任务 #3）。",
        }

    if intent == "pause_task":
        task_id = slots.get("task_id")
        if task_id:
            try:
                task = InspectionTask.objects.get(pk=int(task_id))
                return {
                    "action_type": "update",
                    "target": f"巡检任务 #{task.pk}",
                    "payload": {
                        "task_id": task.pk,
                        "action": "pause",
                        "current_status": task.status,
                        "title": task.title,
                        "timestamp": now,
                    },
                    "response": f"准备暂停任务「{task.title}」（当前状态：{task.get_status_display()}）。请确认执行。",
                }
            except (InspectionTask.DoesNotExist, ValueError):
                pass
        return {
            "action_type": "query",
            "target": "巡检任务",
            "payload": {"action": "pause", "timestamp": now},
            "response": "请指定要暂停的任务 ID（如：暂停任务 #3）。",
        }

    if intent == "navigate":
        page = slots.get("page", "dashboard")
        resolved = PAGE_ALIASES.get(page, page)
        return {
            "action_type": "navigate",
            "target": resolved,
            "payload": {
                "page": resolved,
                "timestamp": now,
            },
            "response": f"正在跳转至「{page}」页面。",
        }

    if intent == "generate_report":
        station_name = slots.get("station", "全部")
        period = slots.get("period", "本月")
        fmt = slots.get("format", "网页")
        task_id = slots.get("task_id")
        task = InspectionTask.objects.filter(id=task_id).first() if task_id else None
        return {
            "action_type": "export",
            "target": "巡检报告",
            "payload": {
                "station": station_name,
                "period": period,
                "format": fmt,
                "task_id": task.id if task else None,
                "task_title": task.title if task else "",
                "timestamp": now,
            },
            "response": (
                f"准备分析巡检任务「{task.title}」（格式：{fmt}）。请确认执行。"
                if task else "请指定已完成的巡检任务编号，例如：生成任务 #3 的 PDF 分析报告。"
            ),
        }

    if intent == "export_data":
        target = slots.get("target", "全部数据")
        fmt = slots.get("format", "Excel")
        return {
            "action_type": "export",
            "target": target,
            "payload": {
                "target": target,
                "format": fmt,
                "timestamp": now,
            },
            "response": f"准备导出{target}（格式：{fmt}）。请确认执行。",
        }

    # help / fallback
    return {
        "action_type": "query",
        "target": "帮助",
        "payload": {
            "timestamp": now,
        },
        "response": (
            "您好！我是绿能先锋智能助手，可以帮您：\n"
            "1️⃣ 查询异常事件 — 如「查询北区异常」\n"
            "2️⃣ 查询巡检任务 — 如「任务进度如何」\n"
            "3️⃣ 查看电站统计 — 如「电站概况」\n"
            "4️⃣ 创建巡检任务 — 如「创建新任务」\n"
            "5️⃣ 开始/暂停任务 — 如「开始任务 #3」\n"
            "6️⃣ 跳转页面 — 如「打开报告中心」\n"
            "7️⃣ 生成报告 — 如「生成本月报告」\n"
            "8️⃣ 导出数据 — 如「导出异常数据」\n\n"
            "查询类问题会直接返回结果；创建任务、生成报告等操作，我会先向您确认。"
        ),
    }
