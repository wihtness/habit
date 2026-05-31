from __future__ import annotations

from datetime import date

from .scheduler import build_default_templates, prepare_day_schedule


def main() -> None:
    today = date.today()
    schedule = prepare_day_schedule(today, build_default_templates())

    print(f"Date: {schedule.date.isoformat()}")
    print(f"Day type: {schedule.day_type.value}")
    print(f"Template: {schedule.template.name}")
    if schedule.warnings:
        print("Warnings:")
        for warning in schedule.warnings:
            print(f"  - {warning}")
    print("Reminder plans:")
    for plan in schedule.reminder_plans:
        print(f"  - {plan.time.strftime('%H:%M')} {plan.name} [{plan.type}]")


if __name__ == "__main__":
    main()
