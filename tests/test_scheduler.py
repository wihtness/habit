from __future__ import annotations

import unittest
from datetime import date, time

from habit import (
    CalendarDayOverride,
    DayType,
    ScheduleTemplate,
    ScheduleTemplateItem,
    TemplateSelectionError,
    build_default_templates,
    materialize_day_schedule,
    prepare_day_schedule,
    resolve_day_type,
    select_schedule_template,
)


class ResolveDayTypeTests(unittest.TestCase):
    def test_returns_workday_for_normal_weekday(self) -> None:
        actual = resolve_day_type(date(2026, 6, 3))
        self.assertEqual(actual, DayType.WORKDAY)

    def test_returns_weekend_for_saturday_without_holiday(self) -> None:
        actual = resolve_day_type(date(2026, 6, 6))
        self.assertEqual(actual, DayType.WEEKEND)

    def test_holiday_beats_weekend(self) -> None:
        saturday_holiday = date(2026, 10, 3)
        actual = resolve_day_type(saturday_holiday, holiday_dates=[saturday_holiday])
        self.assertEqual(actual, DayType.HOLIDAY)

    def test_manual_override_beats_default_rules(self) -> None:
        target = date(2026, 6, 3)
        overrides = {
            target: CalendarDayOverride(
                date=target,
                day_type=DayType.HOLIDAY,
                reason="manual holiday",
            )
        }
        actual = resolve_day_type(target, overrides=overrides)
        self.assertEqual(actual, DayType.HOLIDAY)


class TemplateSelectionTests(unittest.TestCase):
    def test_selects_matching_template(self) -> None:
        templates = build_default_templates()
        selected, warnings = select_schedule_template(DayType.WEEKEND, templates)
        self.assertEqual(selected.day_type, DayType.WEEKEND)
        self.assertEqual(warnings, ())

    def test_falls_back_to_workday_template(self) -> None:
        workday = next(
            template for template in build_default_templates() if template.day_type == DayType.WORKDAY
        )
        selected, warnings = select_schedule_template(DayType.HOLIDAY, [workday])
        self.assertEqual(selected.day_type, DayType.WORKDAY)
        self.assertEqual(warnings, ("template_missing_fallback_to_workday",))

    def test_raises_when_no_enabled_templates_exist(self) -> None:
        disabled = ScheduleTemplate(
            id="disabled",
            name="disabled",
            day_type=DayType.WORKDAY,
            is_enabled=False,
        )
        with self.assertRaises(TemplateSelectionError):
            select_schedule_template(DayType.WORKDAY, [disabled])


class MaterializationTests(unittest.TestCase):
    def test_materialize_keeps_time_and_sort_order(self) -> None:
        template = ScheduleTemplate(
            id="tpl",
            name="test",
            day_type=DayType.WORKDAY,
            items=(
                ScheduleTemplateItem(
                    id="late",
                    name="Late",
                    time=time(16, 0),
                    type="late",
                    goal_context="late",
                    default_action_level="minimum",
                    sort_order=20,
                ),
                ScheduleTemplateItem(
                    id="early-second",
                    name="Early second",
                    time=time(15, 0),
                    type="early",
                    goal_context="early",
                    default_action_level="minimum",
                    sort_order=20,
                ),
                ScheduleTemplateItem(
                    id="early-first",
                    name="Early first",
                    time=time(15, 0),
                    type="early",
                    goal_context="early",
                    default_action_level="minimum",
                    sort_order=10,
                ),
            ),
        )

        plans = materialize_day_schedule(date(2026, 6, 3), template)

        self.assertEqual(
            [plan.template_item_id for plan in plans],
            ["early-first", "early-second", "late"],
        )


class PrepareDayScheduleTests(unittest.TestCase):
    def test_builds_workday_schedule(self) -> None:
        schedule = prepare_day_schedule(date(2026, 6, 3), build_default_templates())
        self.assertEqual(schedule.day_type, DayType.WORKDAY)
        self.assertEqual(schedule.template.day_type, DayType.WORKDAY)
        self.assertEqual(
            [plan.time.strftime("%H:%M") for plan in schedule.reminder_plans],
            ["15:00", "15:20", "15:40", "17:30", "21:15"],
        )

    def test_builds_weekend_schedule(self) -> None:
        schedule = prepare_day_schedule(date(2026, 6, 6), build_default_templates())
        self.assertEqual(schedule.day_type, DayType.WEEKEND)
        self.assertEqual(schedule.template.day_type, DayType.WEEKEND)
        self.assertEqual(
            [plan.time.strftime("%H:%M") for plan in schedule.reminder_plans],
            ["10:30", "16:30", "21:30"],
        )

    def test_holiday_override_changes_template(self) -> None:
        target = date(2026, 6, 3)
        schedule = prepare_day_schedule(
            target,
            build_default_templates(),
            overrides={target: DayType.HOLIDAY},
        )
        self.assertEqual(schedule.day_type, DayType.HOLIDAY)
        self.assertEqual(schedule.template.day_type, DayType.HOLIDAY)
        self.assertEqual(
            [plan.time.strftime("%H:%M") for plan in schedule.reminder_plans],
            ["11:00", "17:00", "21:30"],
        )


if __name__ == "__main__":
    unittest.main()
