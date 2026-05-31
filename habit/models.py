from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum


class DayType(StrEnum):
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class FeedbackType(StrEnum):
    COMPLETED = "completed"
    ESCAPE = "escape"
    BODY_BAD = "body_bad"
    TIRED = "tired"
    NEED_NEXT_STEP = "need_next_step"
    SKIP = "skip"
    NEED_MINIMUM = "need_minimum"
    SLIPPED = "slipped"
    NO_REPLY = "no_reply"


class IntensityLevel(StrEnum):
    NORMAL = "normal"
    DOWNGRADE = "downgrade"
    MINIMUM = "minimum"


class ActionSource(StrEnum):
    RULE = "rule"
    LLM = "llm"


class ReminderRunStatus(StrEnum):
    PENDING_SEND = "pending_send"
    SENT = "sent"
    WAITING_FEEDBACK = "waiting_feedback"
    RESPONDED = "responded"
    AUTO_PROGRESSED = "auto_progressed"
    CLOSED = "closed"
    SEND_FAILED = "send_failed"


class NotificationStatus(StrEnum):
    SENT = "sent"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScheduleTemplateItem:
    id: str
    name: str
    time: time
    type: str
    goal_context: str
    default_action_level: str
    feedback_window_minutes: int = 10
    allow_llm: bool = True
    sort_order: int = 0
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class ScheduleTemplate:
    id: str
    name: str
    day_type: DayType
    description: str = ""
    items: tuple[ScheduleTemplateItem, ...] = ()
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class CalendarDayOverride:
    date: date
    day_type: DayType
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ReminderPlan:
    id: str
    template_item_id: str
    plan_date: date
    name: str
    time: time
    type: str
    goal_context: str
    default_action_level: str
    feedback_window_minutes: int
    allow_llm: bool
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class PreparedDaySchedule:
    date: date
    day_type: DayType
    template: ScheduleTemplate
    reminder_plans: tuple[ReminderPlan, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DayScheduleRecord:
    date: date
    day_type: DayType
    template_id: str
    warning_codes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReminderRun:
    id: str
    plan_id: str
    scheduled_at: datetime
    triggered_at: datetime
    status: ReminderRunStatus
    notification_channel: str
    delivery_message_id: str
    feedback_deadline: datetime
    run_token: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    id: str
    run_id: str
    feedback_type: FeedbackType
    body_signals: tuple[str, ...] = ()
    text_note: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class ActionPlan:
    id: str
    run_id: str
    source: ActionSource
    intensity_level: IntensityLevel
    plan_text: str
    duration_minutes: int
    stop_condition: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class HealthRule:
    id: str
    symptom_type: str
    danger_signals: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    avoid_actions: tuple[str, ...]
    medical_warning: str
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class DailyClosure:
    id: str
    date: date
    summary_text: str
    blockers_text: str
    tomorrow_first_step: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: str
    title: str
    body: str
    link: str
    channel: str
    status: NotificationStatus
    related_run_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True, slots=True)
class ReminderSettings:
    paused_types: tuple[str, ...] = ()
    notifications_paused: bool = False
    max_daily_notifications: int = 20
