from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from .models import (
    ActionPlan,
    CalendarDayOverride,
    DailyClosure,
    DayScheduleRecord,
    DayType,
    FeedbackEvent,
    FeedbackType,
    NotificationRecord,
    NotificationStatus,
    PreparedDaySchedule,
    ReminderPlan,
    ReminderRun,
    ReminderRunStatus,
    ReminderSettings,
    ScheduleTemplate,
)
from .planner import ContextualPlanner
from .rules import RuleEngine
from .scheduler import prepare_day_schedule
from .storage import (
    JsonStateStore,
    action_plan_from_dict,
    daily_closure_from_dict,
    day_schedule_record_from_dict,
    feedback_event_from_dict,
    health_rule_from_dict,
    notification_from_dict,
    override_from_dict,
    reminder_plan_from_dict,
    reminder_run_from_dict,
    serialize_dataclass,
    settings_from_dict,
    template_from_dict,
)


class HabitService:
    def __init__(
        self,
        store: JsonStateStore | None = None,
        *,
        base_url: str = "http://localhost:8000",
    ) -> None:
        self.store = store or JsonStateStore()
        self.base_url = base_url.rstrip("/")
        self.planner = ContextualPlanner()

    def list_templates(self) -> tuple[ScheduleTemplate, ...]:
        state = self.store.load()
        return self._load_templates(state)

    def replace_template(self, template: ScheduleTemplate) -> ScheduleTemplate:
        state = self.store.load()
        templates = [item for item in self._load_templates(state) if item.day_type != template.day_type]
        templates.append(template)
        state["templates"] = [serialize_dataclass(item) for item in templates]
        self.store.save(state)
        return template

    def list_holidays(self) -> tuple[date, ...]:
        state = self.store.load()
        return tuple(date.fromisoformat(item) for item in state.get("holiday_dates", []))

    def replace_holidays(self, holidays: list[date]) -> tuple[date, ...]:
        state = self.store.load()
        deduped = sorted({item.isoformat() for item in holidays})
        state["holiday_dates"] = deduped
        self.store.save(state)
        return tuple(date.fromisoformat(item) for item in deduped)

    def list_overrides(self) -> tuple[CalendarDayOverride, ...]:
        state = self.store.load()
        return self._load_overrides(state)

    def upsert_override(self, override: CalendarDayOverride) -> CalendarDayOverride:
        state = self.store.load()
        overrides = [item for item in self._load_overrides(state) if item.date != override.date]
        overrides.append(override)
        state["overrides"] = [serialize_dataclass(item) for item in sorted(overrides, key=lambda item: item.date)]
        self.store.save(state)
        return override

    def delete_override(self, target_date: date) -> None:
        state = self.store.load()
        overrides = [item for item in self._load_overrides(state) if item.date != target_date]
        state["overrides"] = [serialize_dataclass(item) for item in overrides]
        self.store.save(state)

    def get_settings(self) -> ReminderSettings:
        state = self.store.load()
        return settings_from_dict(state["settings"])

    def update_settings(self, settings: ReminderSettings) -> ReminderSettings:
        state = self.store.load()
        state["settings"] = serialize_dataclass(settings)
        self.store.save(state)
        return settings

    def list_health_rules(self):
        state = self.store.load()
        return self._load_health_rules(state)

    def prepare_day_schedule(self, target_date: date) -> PreparedDaySchedule:
        state = self.store.load()
        prepared = self._prepare_day_schedule_in_state(state, target_date)
        self.store.save(state)
        return prepared

    def get_day_schedule(self, target_date: date) -> PreparedDaySchedule:
        state = self.store.load()
        existing = self._get_day_schedule_from_state(state, target_date)
        if existing is not None:
            return existing
        prepared = self._prepare_day_schedule_in_state(state, target_date)
        self.store.save(state)
        return prepared

    def run_due_reminders(self, now: datetime) -> tuple[ReminderRun, ...]:
        state = self.store.load()
        self._ensure_day_schedule(state, now.date())
        settings = settings_from_dict(state["settings"])
        plans = self._load_reminder_plans(state, now.date())
        runs = self._load_runs(state)
        notifications = self._load_notifications(state)
        sent_today = sum(1 for item in notifications if item.status == NotificationStatus.SENT and item.created_at.date() == now.date())
        existing_plan_ids = {run.plan_id for run in runs}
        created_runs: list[ReminderRun] = []

        for plan in sorted(plans, key=lambda item: item.time):
            if plan.id in existing_plan_ids:
                continue
            if datetime.combine(plan.plan_date, plan.time) > now:
                continue

            if settings.notifications_paused or plan.type in settings.paused_types or sent_today >= settings.max_daily_notifications:
                self._create_notification(
                    state,
                    title=f"提醒已抑制：{plan.name}",
                    body="当前提醒被暂停或超过每日提醒上限。",
                    link="",
                    status=NotificationStatus.SUPPRESSED,
                )
                continue

            run = ReminderRun(
                id=f"run-{uuid4().hex[:12]}",
                plan_id=plan.id,
                scheduled_at=datetime.combine(plan.plan_date, plan.time),
                triggered_at=now,
                status=ReminderRunStatus.WAITING_FEEDBACK,
                notification_channel="local_outbox",
                delivery_message_id="",
                feedback_deadline=now.replace(microsecond=0) + self._minutes_delta(plan.feedback_window_minutes),
                run_token=uuid4().hex,
                created_at=now,
                updated_at=now,
            )
            link = f"{self.base_url}/r/{run.run_token}"
            notification = self._create_notification(
                state,
                title=plan.name,
                body=self._build_notification_body(plan),
                link=link,
                status=NotificationStatus.SENT,
                related_run_id=run.id,
            )
            run = replace(run, delivery_message_id=notification.id)
            runs.append(run)
            created_runs.append(run)
            sent_today += 1

        state["runs"] = [serialize_dataclass(item) for item in runs]
        self.store.save(state)
        return tuple(created_runs)

    def process_auto_progress(self, now: datetime) -> tuple[ActionPlan, ...]:
        state = self.store.load()
        runs = self._load_runs(state)
        feedbacks = self._load_feedback_events(state)
        actions = self._load_action_plans(state)
        plans_by_id = {plan.id: plan for plan in self._load_all_reminder_plans(state)}
        rule_engine = RuleEngine(self._load_health_rules(state))

        feedback_run_ids = {feedback.run_id for feedback in feedbacks}
        action_run_ids = {action.run_id for action in actions}
        new_actions: list[ActionPlan] = []
        updated_runs: list[ReminderRun] = []

        for run in runs:
            if run.status not in {ReminderRunStatus.SENT, ReminderRunStatus.WAITING_FEEDBACK}:
                updated_runs.append(run)
                continue
            if run.feedback_deadline > now:
                updated_runs.append(run)
                continue
            if run.id in feedback_run_ids or run.id in action_run_ids:
                updated_runs.append(run)
                continue

            plan = plans_by_id[run.plan_id]
            action = rule_engine.generate(
                run_id=run.id,
                plan=plan,
                feedback_type=FeedbackType.NO_REPLY,
                now=now,
            )
            actions.append(action)
            new_actions.append(action)
            updated_runs.append(replace(run, status=ReminderRunStatus.AUTO_PROGRESSED, updated_at=now))
            self._create_notification(
                state,
                title=f"默认动作：{plan.name}",
                body=action.plan_text,
                link=f"{self.base_url}/r/{run.run_token}",
                status=NotificationStatus.SENT,
                related_run_id=run.id,
            )

        state["runs"] = [serialize_dataclass(item) for item in updated_runs]
        state["action_plans"] = [serialize_dataclass(item) for item in actions]
        self.store.save(state)
        return tuple(new_actions)

    def submit_feedback(
        self,
        *,
        run_id: str,
        feedback_type: FeedbackType,
        body_signals: tuple[str, ...] = (),
        note: str = "",
        now: datetime | None = None,
    ) -> ActionPlan:
        timestamp = now or datetime.now()
        state = self.store.load()
        runs = self._load_runs(state)
        plans_by_id = {plan.id: plan for plan in self._load_all_reminder_plans(state)}
        run = self._require_run(runs, run_id)
        plan = plans_by_id[run.plan_id]

        feedback = FeedbackEvent(
            id=f"fb-{uuid4().hex[:12]}",
            run_id=run_id,
            feedback_type=feedback_type,
            body_signals=body_signals,
            text_note=note,
            created_at=timestamp,
        )
        feedbacks = self._load_feedback_events(state)
        feedbacks.append(feedback)
        state["feedback_events"] = [serialize_dataclass(item) for item in feedbacks]

        rule_engine = RuleEngine(self._load_health_rules(state))
        action = rule_engine.generate(
            run_id=run_id,
            plan=plan,
            feedback_type=feedback_type,
            body_signals=body_signals,
            note=note,
            now=timestamp,
        )
        if plan.allow_llm and feedback_type in {FeedbackType.NEED_NEXT_STEP, FeedbackType.COMPLETED, FeedbackType.ESCAPE}:
            action = self.planner.generate(
                base_action=action,
                plan=plan,
                feedback_type=feedback_type,
                note=note,
                now=timestamp,
            )

        actions = self._load_action_plans(state)
        actions.append(action)
        state["action_plans"] = [serialize_dataclass(item) for item in actions]
        state["runs"] = [
            serialize_dataclass(replace(item, status=ReminderRunStatus.RESPONDED, updated_at=timestamp))
            if item.id == run_id
            else serialize_dataclass(item)
            for item in runs
        ]
        self.store.save(state)
        return action

    def generate_next_step(self, run_id: str, now: datetime | None = None) -> ActionPlan:
        timestamp = now or datetime.now()
        state = self.store.load()
        runs = self._load_runs(state)
        run = self._require_run(runs, run_id)
        plans_by_id = {plan.id: plan for plan in self._load_all_reminder_plans(state)}
        feedbacks = [item for item in self._load_feedback_events(state) if item.run_id == run_id]
        latest_feedback = feedbacks[-1] if feedbacks else None
        note = latest_feedback.text_note if latest_feedback else ""
        body_signals = latest_feedback.body_signals if latest_feedback else ()
        feedback_type = latest_feedback.feedback_type if latest_feedback else FeedbackType.NEED_NEXT_STEP
        return self.submit_feedback(
            run_id=run_id,
            feedback_type=feedback_type if latest_feedback else FeedbackType.NEED_NEXT_STEP,
            body_signals=body_signals,
            note=note,
            now=timestamp,
        )

    def list_notifications(self) -> tuple[NotificationRecord, ...]:
        state = self.store.load()
        return self._load_notifications(state)

    def get_feedback_context(self, run_token: str) -> dict:
        state = self.store.load()
        runs = self._load_runs(state)
        run = next((item for item in runs if item.run_token == run_token), None)
        if run is None:
            raise KeyError("run_token_not_found")
        plan = next(plan for plan in self._load_all_reminder_plans(state) if plan.id == run.plan_id)
        actions = [item for item in self._load_action_plans(state) if item.run_id == run.id]
        feedbacks = [item for item in self._load_feedback_events(state) if item.run_id == run.id]
        return {
            "run": run,
            "plan": plan,
            "actions": actions,
            "feedbacks": feedbacks,
        }

    def generate_daily_closure(self, target_date: date) -> DailyClosure:
        state = self.store.load()
        runs = [item for item in self._load_runs(state) if item.triggered_at.date() == target_date]
        feedbacks = [item for item in self._load_feedback_events(state) if item.created_at.date() == target_date]
        actions = [item for item in self._load_action_plans(state) if item.created_at.date() == target_date]

        completed = sum(1 for item in feedbacks if item.feedback_type == FeedbackType.COMPLETED)
        slipped = sum(1 for item in feedbacks if item.feedback_type == FeedbackType.SLIPPED)
        body_bad = sum(1 for item in feedbacks if item.feedback_type == FeedbackType.BODY_BAD)
        auto_progressed = sum(1 for item in runs if item.status == ReminderRunStatus.AUTO_PROGRESSED)

        summary_text = (
            f"今天共触发 {len(runs)} 次提醒，完成反馈 {completed} 次，"
            f"自动推进 {auto_progressed} 次，滑坡恢复 {slipped} 次。"
        )
        blockers = []
        if slipped:
            blockers.append("今天出现了滑坡，需要继续优化高风险时段的切断动作。")
        if body_bad:
            blockers.append("今天身体状态干扰了执行，明天要优先恢复。")
        if not blockers:
            blockers.append("今天主要问题不大，保持低阻力推进即可。")
        tomorrow_first_step = actions[-1].stop_condition if actions else "先执行当天第一条最低动作提醒。"

        closure = DailyClosure(
            id=f"cls-{uuid4().hex[:12]}",
            date=target_date,
            summary_text=summary_text,
            blockers_text=" ".join(blockers),
            tomorrow_first_step=tomorrow_first_step,
        )
        closures = [item for item in self._load_daily_closures(state) if item.date != target_date]
        closures.append(closure)
        state["daily_closures"] = [serialize_dataclass(item) for item in closures]
        self._create_notification(
            state,
            title="晚间收口",
            body=f"{closure.summary_text}\n{closure.blockers_text}\n明天第一步：{closure.tomorrow_first_step}",
            link="",
            status=NotificationStatus.SENT,
        )
        self.store.save(state)
        return closure

    def get_logs(self, target_date: date) -> dict:
        state = self.store.load()
        return {
            "day_schedule": self._get_day_schedule_from_state(state, target_date),
            "runs": [item for item in self._load_runs(state) if item.triggered_at.date() == target_date],
            "feedbacks": [item for item in self._load_feedback_events(state) if item.created_at.date() == target_date],
            "actions": [item for item in self._load_action_plans(state) if item.created_at.date() == target_date],
            "notifications": [item for item in self._load_notifications(state) if item.created_at.date() == target_date],
            "closure": next((item for item in self._load_daily_closures(state) if item.date == target_date), None),
        }

    def _prepare_day_schedule_in_state(self, state: dict, target_date: date) -> PreparedDaySchedule:
        templates = self._load_templates(state)
        holidays = [date.fromisoformat(item) for item in state.get("holiday_dates", [])]
        overrides = {item.date: item for item in self._load_overrides(state)}
        prepared = prepare_day_schedule(target_date, templates, holidays, overrides)
        record = DayScheduleRecord(
            date=target_date,
            day_type=prepared.day_type,
            template_id=prepared.template.id,
            warning_codes=prepared.warnings,
        )
        records = [item for item in self._load_day_schedule_records(state) if item.date != target_date]
        records.append(record)
        state["day_schedules"] = [serialize_dataclass(item) for item in sorted(records, key=lambda item: item.date)]

        all_plans = [item for item in self._load_all_reminder_plans(state) if item.plan_date != target_date]
        all_plans.extend(prepared.reminder_plans)
        state["reminder_plans"] = [serialize_dataclass(item) for item in sorted(all_plans, key=lambda item: (item.plan_date, item.time))]
        return prepared

    def _ensure_day_schedule(self, state: dict, target_date: date) -> PreparedDaySchedule:
        existing = self._get_day_schedule_from_state(state, target_date)
        if existing is not None:
            return existing
        return self._prepare_day_schedule_in_state(state, target_date)

    def _get_day_schedule_from_state(self, state: dict, target_date: date) -> PreparedDaySchedule | None:
        record = next((item for item in self._load_day_schedule_records(state) if item.date == target_date), None)
        if record is None:
            return None
        templates = {item.id: item for item in self._load_templates(state)}
        template = templates[record.template_id]
        plans = [item for item in self._load_all_reminder_plans(state) if item.plan_date == target_date]
        return PreparedDaySchedule(
            date=target_date,
            day_type=record.day_type,
            template=template,
            reminder_plans=tuple(sorted(plans, key=lambda item: item.time)),
            warnings=record.warning_codes,
        )

    def _create_notification(
        self,
        state: dict,
        *,
        title: str,
        body: str,
        link: str,
        status: NotificationStatus,
        related_run_id: str = "",
    ) -> NotificationRecord:
        notifications = self._load_notifications(state)
        notification = NotificationRecord(
            id=f"msg-{uuid4().hex[:12]}",
            title=title,
            body=body,
            link=link,
            channel="local_outbox",
            status=status,
            related_run_id=related_run_id,
        )
        notifications.append(notification)
        state["notifications"] = [serialize_dataclass(item) for item in notifications]
        return notification

    def _build_notification_body(self, plan: ReminderPlan) -> str:
        return f"{plan.goal_context}\n点击进入反馈页，或不回复让系统默认推进最低动作。"

    def _load_templates(self, state: dict) -> tuple[ScheduleTemplate, ...]:
        return tuple(template_from_dict(item) for item in state.get("templates", []))

    def _load_overrides(self, state: dict) -> tuple[CalendarDayOverride, ...]:
        return tuple(override_from_dict(item) for item in state.get("overrides", []))

    def _load_day_schedule_records(self, state: dict) -> tuple[DayScheduleRecord, ...]:
        return tuple(day_schedule_record_from_dict(item) for item in state.get("day_schedules", []))

    def _load_all_reminder_plans(self, state: dict) -> tuple[ReminderPlan, ...]:
        return tuple(reminder_plan_from_dict(item) for item in state.get("reminder_plans", []))

    def _load_reminder_plans(self, state: dict, target_date: date) -> tuple[ReminderPlan, ...]:
        return tuple(item for item in self._load_all_reminder_plans(state) if item.plan_date == target_date)

    def _load_runs(self, state: dict) -> list[ReminderRun]:
        return [reminder_run_from_dict(item) for item in state.get("runs", [])]

    def _load_feedback_events(self, state: dict) -> list[FeedbackEvent]:
        return [feedback_event_from_dict(item) for item in state.get("feedback_events", [])]

    def _load_action_plans(self, state: dict) -> list[ActionPlan]:
        return [action_plan_from_dict(item) for item in state.get("action_plans", [])]

    def _load_daily_closures(self, state: dict) -> list[DailyClosure]:
        return [daily_closure_from_dict(item) for item in state.get("daily_closures", [])]

    def _load_notifications(self, state: dict) -> list[NotificationRecord]:
        return [notification_from_dict(item) for item in state.get("notifications", [])]

    def _load_health_rules(self, state: dict):
        return tuple(health_rule_from_dict(item) for item in state.get("health_rules", []))

    def _require_run(self, runs: list[ReminderRun], run_id: str) -> ReminderRun:
        for run in runs:
            if run.id == run_id:
                return run
        raise KeyError("run_not_found")

    def _minutes_delta(self, minutes: int):
        from datetime import timedelta

        return timedelta(minutes=minutes)
