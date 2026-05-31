from __future__ import annotations

from datetime import date, time
from typing import Iterable, Mapping

from .models import (
    CalendarDayOverride,
    DayType,
    PreparedDaySchedule,
    ReminderPlan,
    ScheduleTemplate,
    ScheduleTemplateItem,
)


class TemplateSelectionError(ValueError):
    """Raised when no enabled schedule template can be selected."""


def resolve_day_type(
    target_date: date,
    holiday_dates: Iterable[date] | None = None,
    overrides: Mapping[date, DayType | CalendarDayOverride] | None = None,
) -> DayType:
    """Resolve the operating day type for a date.

    Priority:
    1. Manual one-day override
    2. Holiday date list
    3. Weekend detection
    4. Workday fallback
    """

    override_map = overrides or {}
    if target_date in override_map:
        override_value = override_map[target_date]
        if isinstance(override_value, CalendarDayOverride):
            return override_value.day_type
        return DayType(override_value)

    holiday_set = set(holiday_dates or ())
    if target_date in holiday_set:
        return DayType.HOLIDAY

    if target_date.weekday() >= 5:
        return DayType.WEEKEND

    return DayType.WORKDAY


def select_schedule_template(
    day_type: DayType,
    templates: Iterable[ScheduleTemplate],
) -> tuple[ScheduleTemplate, tuple[str, ...]]:
    """Select the enabled template for a day type, with workday fallback."""

    enabled_templates = [template for template in templates if template.is_enabled]
    selected = _find_enabled_template(enabled_templates, day_type)
    if selected is not None:
        return selected, ()

    fallback = _find_enabled_template(enabled_templates, DayType.WORKDAY)
    if fallback is not None:
        return fallback, ("template_missing_fallback_to_workday",)

    raise TemplateSelectionError(
        f"No enabled template available for {day_type.value} and no workday fallback."
    )


def materialize_day_schedule(
    target_date: date,
    template: ScheduleTemplate,
) -> tuple[ReminderPlan, ...]:
    """Turn template items into date-bound reminder plans."""

    enabled_items = [item for item in template.items if item.is_enabled]
    sorted_items = sorted(enabled_items, key=lambda item: (item.time, item.sort_order, item.id))

    plans = []
    for item in sorted_items:
        plans.append(
            ReminderPlan(
                id=f"{target_date.isoformat()}::{item.id}",
                template_item_id=item.id,
                plan_date=target_date,
                name=item.name,
                time=item.time,
                type=item.type,
                goal_context=item.goal_context,
                default_action_level=item.default_action_level,
                feedback_window_minutes=item.feedback_window_minutes,
                allow_llm=item.allow_llm,
                is_enabled=True,
            )
        )

    return tuple(plans)


def prepare_day_schedule(
    target_date: date,
    templates: Iterable[ScheduleTemplate],
    holiday_dates: Iterable[date] | None = None,
    overrides: Mapping[date, DayType | CalendarDayOverride] | None = None,
) -> PreparedDaySchedule:
    """Resolve day type, select a template, and materialize plans for a date."""

    day_type = resolve_day_type(
        target_date=target_date,
        holiday_dates=holiday_dates,
        overrides=overrides,
    )
    template, warnings = select_schedule_template(day_type=day_type, templates=templates)
    reminder_plans = materialize_day_schedule(target_date=target_date, template=template)

    return PreparedDaySchedule(
        date=target_date,
        day_type=day_type,
        template=template,
        reminder_plans=reminder_plans,
        warnings=warnings,
    )


def build_default_templates() -> tuple[ScheduleTemplate, ...]:
    """Build the project's first-pass default templates.

    Weekend and holiday defaults are intentionally lightweight and can be
    refined later without changing the scheduling core.
    """

    workday = ScheduleTemplate(
        id="tpl-workday",
        name="工作日模板",
        day_type=DayType.WORKDAY,
        description="聚焦下午防滑坡、低阻力重启和夜间收口。",
        items=(
            _item(
                "workday-cut-off",
                "收盘后切断提醒",
                "15:00",
                "cutoff",
                "离开高刺激环境",
                "minimum",
                sort_order=10,
            ),
            _item(
                "workday-energy",
                "补能量提醒",
                "15:20",
                "energy",
                "防止低能量导致找刺激",
                "minimum",
                sort_order=20,
            ),
            _item(
                "workday-restart",
                "二次启动提醒",
                "15:40",
                "restart",
                "回到 20 分钟最小任务",
                "downgrade",
                sort_order=30,
            ),
            _item(
                "workday-dispatch",
                "下班调度",
                "17:30",
                "dispatch",
                "判断是否继续推进",
                "downgrade",
                sort_order=40,
            ),
            _item(
                "workday-closure",
                "晚上收口",
                "21:15",
                "closure",
                "停止过热并准备明天",
                "minimum",
                sort_order=50,
            ),
        ),
    )

    weekend = ScheduleTemplate(
        id="tpl-weekend",
        name="普通休息日模板",
        day_type=DayType.WEEKEND,
        description="优先恢复、轻训练和低压力的能力维护。",
        items=(
            _item(
                "weekend-recovery",
                "恢复与补能量",
                "10:30",
                "recovery",
                "先补水、补能量并检查身体状态",
                "minimum",
                sort_order=10,
            ),
            _item(
                "weekend-training",
                "轻训练或表达训练",
                "16:30",
                "practice",
                "按状态决定轻训练、表达训练或内容沉淀",
                "downgrade",
                sort_order=20,
            ),
            _item(
                "weekend-closure",
                "休息日收口",
                "21:30",
                "closure",
                "避免夜晚失控并整理明天第一步",
                "minimum",
                sort_order=30,
            ),
        ),
    )

    holiday = ScheduleTemplate(
        id="tpl-holiday",
        name="节假日模板",
        day_type=DayType.HOLIDAY,
        description="优先休息保护、节奏恢复和最低闭环。",
        items=(
            _item(
                "holiday-reset",
                "假期节奏恢复",
                "11:00",
                "reset",
                "避免直接失控，先恢复节奏和身体状态",
                "minimum",
                sort_order=10,
            ),
            _item(
                "holiday-min-loop",
                "假期最低闭环",
                "17:00",
                "minimum_loop",
                "只维持一个最低闭环，不扩展任务",
                "minimum",
                sort_order=20,
            ),
            _item(
                "holiday-closure",
                "假期收口",
                "21:30",
                "closure",
                "避免过热，准备回到稳定节奏",
                "minimum",
                sort_order=30,
            ),
        ),
    )

    return (workday, weekend, holiday)


def _find_enabled_template(
    templates: Iterable[ScheduleTemplate],
    day_type: DayType,
) -> ScheduleTemplate | None:
    for template in templates:
        if template.day_type == day_type:
            return template
    return None


def _item(
    item_id: str,
    name: str,
    hhmm: str,
    item_type: str,
    goal_context: str,
    default_action_level: str,
    *,
    feedback_window_minutes: int = 10,
    allow_llm: bool = True,
    sort_order: int = 0,
) -> ScheduleTemplateItem:
    hour_str, minute_str = hhmm.split(":")
    return ScheduleTemplateItem(
        id=item_id,
        name=name,
        time=time(hour=int(hour_str), minute=int(minute_str)),
        type=item_type,
        goal_context=goal_context,
        default_action_level=default_action_level,
        feedback_window_minutes=feedback_window_minutes,
        allow_llm=allow_llm,
        sort_order=sort_order,
        is_enabled=True,
    )
