from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from habit.api import create_app


class ApiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        data_path = Path(self.tempdir.name) / "state.json"
        self.client = TestClient(create_app(data_path=data_path, base_url="http://testserver"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_prepare_schedule_and_list_templates(self) -> None:
        templates = self.client.get("/api/templates")
        self.assertEqual(templates.status_code, 200)
        self.assertEqual(len(templates.json()), 3)

        prepared = self.client.post("/api/day-schedule/prepare", params={"target_date": "2026-06-03"})
        self.assertEqual(prepared.status_code, 200)
        payload = prepared.json()
        self.assertEqual(payload["day_type"], "workday")
        self.assertEqual(len(payload["reminder_plans"]), 5)

    def test_run_due_and_submit_feedback(self) -> None:
        self.client.post("/api/day-schedule/prepare", params={"target_date": "2026-06-03"})
        due = self.client.post("/api/reminders/run-due", params={"now": "2026-06-03T15:00:00"})
        self.assertEqual(due.status_code, 200)
        runs = due.json()
        self.assertEqual(len(runs), 1)

        outbox = self.client.get("/api/notifications/outbox")
        self.assertEqual(outbox.status_code, 200)
        self.assertEqual(len(outbox.json()), 1)

        feedback = self.client.post(
            f"/api/runs/{runs[0]['id']}/feedback",
            json={
                "feedback_type": "need_next_step",
                "body_signals": [],
                "note": "先只做测试清单",
            },
        )
        self.assertEqual(feedback.status_code, 200)
        action = feedback.json()
        self.assertIn("测试清单", action["plan_text"])
        self.assertIn(action["source"], {"rule", "llm"})

    def test_auto_progress_and_closure_generation(self) -> None:
        self.client.post("/api/day-schedule/prepare", params={"target_date": "2026-06-03"})
        due = self.client.post("/api/reminders/run-due", params={"now": "2026-06-03T15:00:00"})
        self.assertEqual(due.status_code, 200)

        auto = self.client.post("/api/runs/auto-progress", params={"now": "2026-06-03T15:11:00"})
        self.assertEqual(auto.status_code, 200)
        actions = auto.json()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["source"], "rule")

        closure = self.client.post("/api/daily-closure/generate", params={"target_date": "2026-06-03"})
        self.assertEqual(closure.status_code, 200)
        closure_payload = closure.json()
        self.assertIn("今天共触发", closure_payload["summary_text"])

        logs = self.client.get("/api/logs/2026-06-03")
        self.assertEqual(logs.status_code, 200)
        logs_payload = logs.json()
        self.assertEqual(len(logs_payload["actions"]), 1)
        self.assertIsNotNone(logs_payload["closure"])


if __name__ == "__main__":
    unittest.main()
