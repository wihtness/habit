from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .models import ActionPlan, ActionSource, FeedbackType, ReminderPlan


class ContextualPlanner:
    """Local planner that mimics the constrained output shape of an LLM layer."""

    def generate(
        self,
        *,
        base_action: ActionPlan,
        plan: ReminderPlan,
        feedback_type: FeedbackType,
        note: str = "",
        now: datetime | None = None,
    ) -> ActionPlan:
        timestamp = now or datetime.now()
        note_hint = f" 用户补充：{note.strip()}。" if note.strip() else ""
        if feedback_type == FeedbackType.NEED_NEXT_STEP:
            plan_text = (
                f"接下来 {base_action.duration_minutes} 分钟只围绕“{plan.goal_context}”推进。"
                "\n1. 先把无关页面关掉。"
                f"\n2. 只做和“{plan.name}”直接相关的一步。"
                "\n3. 中途不修边角、不扩展范围。"
                f"\n4. 到点后记录结果。{note_hint}"
            )
        elif feedback_type == FeedbackType.COMPLETED:
            plan_text = (
                "你已经完成当前动作，接下来只做收束或一个补充小步。"
                "\n1. 写下这次完成结果。"
                "\n2. 写下当前卡点。"
                f"\n3. 如果还想继续，只围绕“{plan.goal_context}”补一个小闭环。{note_hint}"
            )
        else:
            plan_text = f"{base_action.plan_text}{note_hint}"

        return replace(
            base_action,
            source=ActionSource.LLM,
            plan_text=plan_text,
            created_at=timestamp,
        )
