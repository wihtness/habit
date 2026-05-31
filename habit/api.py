from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .models import CalendarDayOverride, DayType, FeedbackType, ReminderSettings, ScheduleTemplate, ScheduleTemplateItem
from .service import HabitService
from .storage import JsonStateStore, serialize_dataclass


class TemplateItemPayload(BaseModel):
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


class TemplatePayload(BaseModel):
    id: str
    name: str
    description: str = ""
    is_enabled: bool = True
    items: list[TemplateItemPayload]


class OverridePayload(BaseModel):
    date: date
    day_type: DayType
    reason: str = ""


class HolidaysPayload(BaseModel):
    dates: list[date]


class SettingsPayload(BaseModel):
    paused_types: list[str] = Field(default_factory=list)
    notifications_paused: bool = False
    max_daily_notifications: int = 20


class FeedbackPayload(BaseModel):
    feedback_type: FeedbackType
    body_signals: list[str] = Field(default_factory=list)
    note: str = ""


def create_app(
    *,
    data_path: str | Path | None = None,
    base_url: str = "http://localhost:8000",
) -> FastAPI:
    app = FastAPI(title="Habit Execution Supervisor", version="0.1.0")
    service = HabitService(JsonStateStore(data_path), base_url=base_url)
    app.state.service = service

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
        <html>
          <head>
            <meta charset="utf-8" />
            <title>Habit Supervisor</title>
            <style>
              body { font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 16px; line-height: 1.6; }
              code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
              a { color: #0f766e; }
            </style>
          </head>
          <body>
            <h1>Habit Execution Supervisor</h1>
            <p>这是当前 MVP 的本地服务入口。</p>
            <ul>
              <li><a href="/api/templates">查看模板</a></li>
              <li><a href="/api/notifications/outbox">查看通知 outbox</a></li>
              <li><a href="/api/health-rules">查看健康规则</a></li>
            </ul>
            <p>推荐先调用 <code>POST /api/day-schedule/prepare?target_date=YYYY-MM-DD</code>，再调用 <code>POST /api/reminders/run-due</code>。</p>
          </body>
        </html>
        """

    @app.get("/api/templates")
    def list_templates():
        return [serialize_dataclass(item) for item in service.list_templates()]

    @app.put("/api/templates/{day_type}")
    def replace_template(day_type: DayType, payload: TemplatePayload):
        template = ScheduleTemplate(
            id=payload.id,
            name=payload.name,
            day_type=day_type,
            description=payload.description,
            is_enabled=payload.is_enabled,
            items=tuple(
                ScheduleTemplateItem(
                    id=item.id,
                    name=item.name,
                    time=item.time,
                    type=item.type,
                    goal_context=item.goal_context,
                    default_action_level=item.default_action_level,
                    feedback_window_minutes=item.feedback_window_minutes,
                    allow_llm=item.allow_llm,
                    sort_order=item.sort_order,
                    is_enabled=item.is_enabled,
                )
                for item in payload.items
            ),
        )
        return serialize_dataclass(service.replace_template(template))

    @app.get("/api/holidays")
    def list_holidays():
        return [item.isoformat() for item in service.list_holidays()]

    @app.put("/api/holidays")
    def replace_holidays(payload: HolidaysPayload):
        return [item.isoformat() for item in service.replace_holidays(payload.dates)]

    @app.get("/api/overrides")
    def list_overrides():
        return [serialize_dataclass(item) for item in service.list_overrides()]

    @app.post("/api/overrides")
    def upsert_override(payload: OverridePayload):
        override = CalendarDayOverride(
            date=payload.date,
            day_type=payload.day_type,
            reason=payload.reason,
        )
        return serialize_dataclass(service.upsert_override(override))

    @app.delete("/api/overrides/{target_date}")
    def delete_override(target_date: date):
        service.delete_override(target_date)
        return {"deleted": target_date.isoformat()}

    @app.get("/api/settings")
    def get_settings():
        return serialize_dataclass(service.get_settings())

    @app.put("/api/settings")
    def update_settings(payload: SettingsPayload):
        settings = ReminderSettings(
            paused_types=tuple(payload.paused_types),
            notifications_paused=payload.notifications_paused,
            max_daily_notifications=payload.max_daily_notifications,
        )
        return serialize_dataclass(service.update_settings(settings))

    @app.get("/api/health-rules")
    def list_health_rules():
        return [serialize_dataclass(item) for item in service.list_health_rules()]

    @app.post("/api/day-schedule/prepare")
    def prepare_schedule(target_date: date = Query(...)):
        return serialize_dataclass(service.prepare_day_schedule(target_date))

    @app.get("/api/day-schedule/{target_date}")
    def get_schedule(target_date: date):
        return serialize_dataclass(service.get_day_schedule(target_date))

    @app.post("/api/reminders/run-due")
    def run_due(now: datetime = Query(...)):
        return [serialize_dataclass(item) for item in service.run_due_reminders(now)]

    @app.post("/api/runs/auto-progress")
    def auto_progress(now: datetime = Query(...)):
        return [serialize_dataclass(item) for item in service.process_auto_progress(now)]

    @app.get("/api/notifications/outbox")
    def outbox():
        return [serialize_dataclass(item) for item in service.list_notifications()]

    @app.get("/r/{run_token}", response_class=HTMLResponse)
    def feedback_page(run_token: str) -> str:
        try:
            context = service.get_feedback_context(run_token)
        except KeyError:
            raise HTTPException(status_code=404, detail="run_token_not_found")

        run = context["run"]
        plan = context["plan"]
        latest_action = context["actions"][-1].plan_text if context["actions"] else "还没有生成动作。"
        return f"""
        <html>
          <head>
            <meta charset="utf-8" />
            <title>{plan.name}</title>
            <style>
              body {{ font-family: 'Segoe UI', sans-serif; max-width: 760px; margin: 24px auto; padding: 0 16px; background: #f8fafc; color: #0f172a; }}
              .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 24px rgba(15,23,42,0.08); margin-bottom: 16px; }}
              button {{ margin: 6px 6px 0 0; padding: 10px 14px; border-radius: 10px; border: none; background: #0f766e; color: white; cursor: pointer; }}
              textarea {{ width: 100%; min-height: 80px; }}
              pre {{ white-space: pre-wrap; background: #f1f5f9; padding: 12px; border-radius: 12px; }}
            </style>
          </head>
          <body>
            <div class="card">
              <h1>{plan.name}</h1>
              <p><strong>目标：</strong>{plan.goal_context}</p>
              <p><strong>默认动作级别：</strong>{plan.default_action_level}</p>
              <p><strong>当前状态：</strong>{run.status.value}</p>
            </div>
            <div class="card">
              <h2>快速反馈</h2>
              <textarea id="note" placeholder="可选备注"></textarea>
              <p>身体信号可用逗号分隔，例如：鼻塞, 牙痛</p>
              <input id="signals" style="width:100%;" placeholder="可选身体信号" />
              <div>
                <button onclick="sendFeedback('completed')">已完成</button>
                <button onclick="sendFeedback('escape')">想逃避</button>
                <button onclick="sendFeedback('body_bad')">身体差</button>
                <button onclick="sendFeedback('tired')">脑子累</button>
                <button onclick="sendFeedback('need_next_step')">继续安排</button>
                <button onclick="sendFeedback('skip')">跳过</button>
                <button onclick="sendFeedback('need_minimum')">给我最低动作</button>
                <button onclick="sendFeedback('slipped')">我已经滑坡了</button>
              </div>
            </div>
            <div class="card">
              <h2>最新动作</h2>
              <pre id="result">{latest_action}</pre>
            </div>
            <script>
              async function sendFeedback(kind) {{
                const note = document.getElementById('note').value;
                const signals = document.getElementById('signals').value
                  .split(',')
                  .map(item => item.trim())
                  .filter(Boolean);
                const response = await fetch('/api/runs/{run.id}/feedback', {{
                  method: 'POST',
                  headers: {{ 'Content-Type': 'application/json' }},
                  body: JSON.stringify({{ feedback_type: kind, note: note, body_signals: signals }})
                }});
                const data = await response.json();
                document.getElementById('result').innerText = data.plan_text || JSON.stringify(data, null, 2);
              }}
            </script>
          </body>
        </html>
        """

    @app.post("/api/runs/{run_id}/feedback")
    def submit_feedback(run_id: str, payload: FeedbackPayload):
        try:
            action = service.submit_feedback(
                run_id=run_id,
                feedback_type=payload.feedback_type,
                body_signals=tuple(payload.body_signals),
                note=payload.note,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="run_not_found")
        return serialize_dataclass(action)

    @app.post("/api/runs/{run_id}/next-step")
    def next_step(run_id: str):
        try:
            action = service.generate_next_step(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="run_not_found")
        return serialize_dataclass(action)

    @app.get("/api/logs/{target_date}")
    def logs(target_date: date):
        data = service.get_logs(target_date)
        return {
            "day_schedule": serialize_dataclass(data["day_schedule"]) if data["day_schedule"] else None,
            "runs": [serialize_dataclass(item) for item in data["runs"]],
            "feedbacks": [serialize_dataclass(item) for item in data["feedbacks"]],
            "actions": [serialize_dataclass(item) for item in data["actions"]],
            "notifications": [serialize_dataclass(item) for item in data["notifications"]],
            "closure": serialize_dataclass(data["closure"]) if data["closure"] else None,
        }

    @app.post("/api/daily-closure/generate")
    def generate_closure(target_date: date = Query(...)):
        return serialize_dataclass(service.generate_daily_closure(target_date))

    return app


app = create_app()
