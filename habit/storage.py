from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Any

from .defaults import build_default_health_rules
from .models import (
    ActionPlan,
    ActionSource,
    CalendarDayOverride,
    DailyClosure,
    DayScheduleRecord,
    DayType,
    FeedbackEvent,
    FeedbackType,
    HealthRule,
    IntensityLevel,
    NotificationRecord,
    NotificationStatus,
    ReminderPlan,
    ReminderRun,
    ReminderRunStatus,
    ReminderSettings,
    ScheduleTemplate,
    ScheduleTemplateItem,
)
from .scheduler import build_default_templates


class JsonStateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or "data/state.json")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            state = self._default_state()
            self.save(state)
            return state
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _default_state(self) -> dict[str, Any]:
        return {
            "templates": [serialize_dataclass(template) for template in build_default_templates()],
            "holiday_dates": [],
            "overrides": [],
            "day_schedules": [],
            "reminder_plans": [],
            "runs": [],
            "feedback_events": [],
            "action_plans": [],
            "daily_closures": [],
            "notifications": [],
            "health_rules": [serialize_dataclass(rule) for rule in build_default_health_rules()],
            "settings": serialize_dataclass(ReminderSettings()),
        }


def serialize_dataclass(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: serialize_dataclass(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [serialize_dataclass(item) for item in value]
    if isinstance(value, list):
        return [serialize_dataclass(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_dataclass(item) for key, item in value.items()}
    return value


def template_from_dict(data: dict[str, Any]) -> ScheduleTemplate:
    return ScheduleTemplate(
        id=data["id"],
        name=data["name"],
        day_type=DayType(data["day_type"]),
        description=data.get("description", ""),
        items=tuple(template_item_from_dict(item) for item in data.get("items", [])),
        is_enabled=data.get("is_enabled", True),
    )


def template_item_from_dict(data: dict[str, Any]) -> ScheduleTemplateItem:
    return ScheduleTemplateItem(
        id=data["id"],
        name=data["name"],
        time=time.fromisoformat(data["time"]),
        type=data["type"],
        goal_context=data["goal_context"],
        default_action_level=data["default_action_level"],
        feedback_window_minutes=data.get("feedback_window_minutes", 10),
        allow_llm=data.get("allow_llm", True),
        sort_order=data.get("sort_order", 0),
        is_enabled=data.get("is_enabled", True),
    )


def override_from_dict(data: dict[str, Any]) -> CalendarDayOverride:
    return CalendarDayOverride(
        date=date.fromisoformat(data["date"]),
        day_type=DayType(data["day_type"]),
        reason=data.get("reason", ""),
    )


def reminder_plan_from_dict(data: dict[str, Any]) -> ReminderPlan:
    return ReminderPlan(
        id=data["id"],
        template_item_id=data["template_item_id"],
        plan_date=date.fromisoformat(data["plan_date"]),
        name=data["name"],
        time=time.fromisoformat(data["time"]),
        type=data["type"],
        goal_context=data["goal_context"],
        default_action_level=data["default_action_level"],
        feedback_window_minutes=data["feedback_window_minutes"],
        allow_llm=data["allow_llm"],
        is_enabled=data.get("is_enabled", True),
    )


def day_schedule_record_from_dict(data: dict[str, Any]) -> DayScheduleRecord:
    return DayScheduleRecord(
        date=date.fromisoformat(data["date"]),
        day_type=DayType(data["day_type"]),
        template_id=data["template_id"],
        warning_codes=tuple(data.get("warning_codes", [])),
    )


def reminder_run_from_dict(data: dict[str, Any]) -> ReminderRun:
    return ReminderRun(
        id=data["id"],
        plan_id=data["plan_id"],
        scheduled_at=datetime.fromisoformat(data["scheduled_at"]),
        triggered_at=datetime.fromisoformat(data["triggered_at"]),
        status=ReminderRunStatus(data["status"]),
        notification_channel=data["notification_channel"],
        delivery_message_id=data["delivery_message_id"],
        feedback_deadline=datetime.fromisoformat(data["feedback_deadline"]),
        run_token=data["run_token"],
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def feedback_event_from_dict(data: dict[str, Any]) -> FeedbackEvent:
    return FeedbackEvent(
        id=data["id"],
        run_id=data["run_id"],
        feedback_type=FeedbackType(data["feedback_type"]),
        body_signals=tuple(data.get("body_signals", [])),
        text_note=data.get("text_note", ""),
        created_at=datetime.fromisoformat(data["created_at"]),
    )


def action_plan_from_dict(data: dict[str, Any]) -> ActionPlan:
    return ActionPlan(
        id=data["id"],
        run_id=data["run_id"],
        source=ActionSource(data["source"]),
        intensity_level=IntensityLevel(data["intensity_level"]),
        plan_text=data["plan_text"],
        duration_minutes=data["duration_minutes"],
        stop_condition=data["stop_condition"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )


def health_rule_from_dict(data: dict[str, Any]) -> HealthRule:
    return HealthRule(
        id=data["id"],
        symptom_type=data["symptom_type"],
        danger_signals=tuple(data.get("danger_signals", [])),
        recommended_actions=tuple(data.get("recommended_actions", [])),
        avoid_actions=tuple(data.get("avoid_actions", [])),
        medical_warning=data["medical_warning"],
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def daily_closure_from_dict(data: dict[str, Any]) -> DailyClosure:
    return DailyClosure(
        id=data["id"],
        date=date.fromisoformat(data["date"]),
        summary_text=data["summary_text"],
        blockers_text=data["blockers_text"],
        tomorrow_first_step=data["tomorrow_first_step"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )


def notification_from_dict(data: dict[str, Any]) -> NotificationRecord:
    return NotificationRecord(
        id=data["id"],
        title=data["title"],
        body=data["body"],
        link=data["link"],
        channel=data["channel"],
        status=NotificationStatus(data["status"]),
        related_run_id=data.get("related_run_id", ""),
        created_at=datetime.fromisoformat(data["created_at"]),
    )


def settings_from_dict(data: dict[str, Any]) -> ReminderSettings:
    return ReminderSettings(
        paused_types=tuple(data.get("paused_types", [])),
        notifications_paused=data.get("notifications_paused", False),
        max_daily_notifications=data.get("max_daily_notifications", 20),
    )
