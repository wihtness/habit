from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from .models import (
    ActionPlan,
    ActionSource,
    FeedbackType,
    HealthRule,
    IntensityLevel,
    ReminderPlan,
)


class RuleEngine:
    def __init__(self, health_rules: tuple[HealthRule, ...]) -> None:
        self.health_rules = health_rules

    def generate(
        self,
        *,
        run_id: str,
        plan: ReminderPlan,
        feedback_type: FeedbackType,
        body_signals: tuple[str, ...] = (),
        note: str = "",
        now: datetime | None = None,
    ) -> ActionPlan:
        timestamp = now or datetime.now()

        if feedback_type == FeedbackType.SLIPPED:
            return self._build_action(
                run_id=run_id,
                source=ActionSource.RULE,
                intensity=IntensityLevel.MINIMUM,
                lines=(
                    "现在不要自责，先执行恢复协议：",
                    "1. 站起来并离开当前位置 3 分钟。",
                    "2. 喝水，手机放远。",
                    "3. 写一句“我现在回来要做的第一步是____”。",
                    "4. 回来后只做一个 10 到 20 分钟的小任务。",
                ),
                duration=15,
                stop_condition="写下第一步并完成一个最小任务后停止。",
                created_at=timestamp,
            )

        if feedback_type in {FeedbackType.BODY_BAD, FeedbackType.TIRED}:
            lines, duration = self._build_recovery_lines(plan, body_signals)
            return self._build_action(
                run_id=run_id,
                source=ActionSource.RULE,
                intensity=IntensityLevel.MINIMUM,
                lines=lines,
                duration=duration,
                stop_condition="完成恢复动作并重新评估状态后停止。",
                created_at=timestamp,
            )

        if feedback_type in {FeedbackType.NO_REPLY, FeedbackType.NEED_MINIMUM, FeedbackType.SKIP}:
            return self._build_action(
                run_id=run_id,
                source=ActionSource.RULE,
                intensity=IntensityLevel.MINIMUM,
                lines=self._minimum_restart_lines(plan),
                duration=20,
                stop_condition="只做完最低动作或一个 20 分钟小闭环就停止。",
                created_at=timestamp,
            )

        if feedback_type == FeedbackType.ESCAPE:
            return self._build_action(
                run_id=run_id,
                source=ActionSource.RULE,
                intensity=IntensityLevel.DOWNGRADE,
                lines=(
                    "你现在不要扩展任务，先降低门槛：",
                    "1. 离开屏幕 5 分钟并喝水。",
                    "2. 回来后只打开最小任务入口。",
                    f"3. 接下来只做和“{plan.goal_context}”直接相关的一小步。",
                ),
                duration=20,
                stop_condition="只推进一个最小步骤，不修边角问题。",
                created_at=timestamp,
            )

        if feedback_type == FeedbackType.COMPLETED:
            return self._build_action(
                run_id=run_id,
                source=ActionSource.RULE,
                intensity=IntensityLevel.DOWNGRADE,
                lines=(
                    "当前动作已完成，接下来只做收束或下一小步：",
                    "1. 记录这次完成了什么。",
                    "2. 写下当前卡点。",
                    "3. 如果状态还行，只推进一个新的最小闭环。",
                ),
                duration=15,
                stop_condition="记录完成结果和下一步后停止。",
                created_at=timestamp,
            )

        return self._build_action(
            run_id=run_id,
            source=ActionSource.RULE,
            intensity=IntensityLevel.DOWNGRADE,
            lines=(
                f"接下来围绕“{plan.goal_context}”只做一个小闭环：",
                "1. 先清空无关页面和干扰。",
                "2. 只做一件当前最短路径的事。",
                "3. 到时间就停，不扩展任务。",
            ),
            duration=30,
            stop_condition="完成一个小闭环或到 30 分钟即停止。",
            created_at=timestamp,
        )

    def _build_recovery_lines(
        self,
        plan: ReminderPlan,
        body_signals: tuple[str, ...],
    ) -> tuple[tuple[str, ...], int]:
        rule = self._find_health_rule(body_signals)
        if rule is None:
            return (
                "现在优先恢复，不推进强任务：",
                "1. 喝水并离开屏幕 5 分钟。",
                "2. 补一点能量或做轻恢复动作。",
                f"3. 如果稍微恢复，再回到“{plan.goal_context}”的最低版本。",
            ), 20

        recommended = "、".join(rule.recommended_actions[:3])
        avoid = "、".join(rule.avoid_actions[:2]) if rule.avoid_actions else "无"
        return (
            f"当前先按“{rule.symptom_type}”处理：",
            f"1. 先做：{recommended}。",
            f"2. 暂时避免：{avoid}。",
            f"3. 如仍不适，只保留“{plan.goal_context}”的最低动作。",
            f"4. 提醒：{rule.medical_warning}",
        ), 15

    def _minimum_restart_lines(self, plan: ReminderPlan) -> tuple[str, ...]:
        if plan.type == "closure":
            return (
                "现在先收口，不需要继续扛：",
                "1. 关掉继续扩展任务的页面。",
                "2. 写三行：今天完成、当前卡点、明天第一步。",
                "3. 如果身体不适，优先降温、洗澡、准备睡眠。",
            )

        if plan.type in {"energy", "recovery"}:
            return (
                "现在先补能量和恢复：",
                "1. 喝水。",
                "2. 补一份低负担食物，比如奶、蛋、面包、水果或坚果。",
                "3. 10 分钟后再决定是否进入最小任务。",
            )

        return (
            "现在不需要思考太多，先做最低动作：",
            "1. 关闭无关页面。",
            "2. 离开屏幕并喝水 5 到 10 分钟。",
            "3. 回来后只做一个最小任务，不开新项目。",
        )

    def _find_health_rule(self, body_signals: tuple[str, ...]) -> HealthRule | None:
        if not body_signals:
            return None
        for signal in body_signals:
            signal_lower = signal.lower()
            for rule in self.health_rules:
                if signal in rule.symptom_type or signal_lower in rule.symptom_type.lower():
                    return rule
        return None

    def _build_action(
        self,
        *,
        run_id: str,
        source: ActionSource,
        intensity: IntensityLevel,
        lines: tuple[str, ...],
        duration: int,
        stop_condition: str,
        created_at: datetime,
    ) -> ActionPlan:
        return ActionPlan(
            id=f"act-{uuid4().hex[:12]}",
            run_id=run_id,
            source=source,
            intensity_level=intensity,
            plan_text="\n".join(lines),
            duration_minutes=duration,
            stop_condition=stop_condition,
            created_at=created_at,
        )
