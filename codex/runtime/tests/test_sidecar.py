"""Tests for the Sidecar event bus, phase wrapper, and doctor preflight."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import sidecar_events  # noqa: E402


class SidecarEnvironment(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("ADANT_SOCIAL_DATA_DIR")
        os.environ["ADANT_SOCIAL_DATA_DIR"] = self._tmp.name
        self._old_no_sidecar = os.environ.get("ADANT_NO_SIDECAR")
        os.environ["ADANT_NO_SIDECAR"] = "1"

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("ADANT_SOCIAL_DATA_DIR", None)
        else:
            os.environ["ADANT_SOCIAL_DATA_DIR"] = self._old
        if self._old_no_sidecar is None:
            os.environ.pop("ADANT_NO_SIDECAR", None)
        else:
            os.environ["ADANT_NO_SIDECAR"] = self._old_no_sidecar
        self._tmp.cleanup()

    def events(self) -> list[dict]:
        path = Path(self._tmp.name) / "progress" / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class EmitTests(SidecarEnvironment):
    def test_emit_appends_valid_json_lines(self) -> None:
        self.assertTrue(sidecar_events.emit("doctor", "start", "hello"))
        self.assertTrue(
            sidecar_events.emit(
                "platform-tiktok",
                "progress",
                "query 3/5",
                skill="browse-tiktok-research",
                counts={"videos": 47},
            )
        )
        events = self.events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["phase"], "doctor")
        self.assertEqual(events[1]["counts"], {"videos": 47})
        self.assertEqual(events[1]["skill"], "browse-tiktok-research")
        for event in events:
            self.assertRegex(event["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_invalid_status_downgrades_to_progress(self) -> None:
        self.assertTrue(sidecar_events.emit("x", "bogus", "m"))
        self.assertEqual(self.events()[0]["status"], "progress")

    def test_warning_is_a_valid_terminal_status(self) -> None:
        self.assertTrue(sidecar_events.emit("x", "warning", "fallback exhausted"))
        self.assertEqual(self.events()[0]["status"], "warning")

    def test_long_message_is_truncated(self) -> None:
        self.assertTrue(sidecar_events.emit("x", "progress", "a" * 2000))
        self.assertEqual(len(self.events()[0]["message"]), 500)

    def test_cli_emits(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "sidecar_events.py"), "doctor", "done", "ok", "--count", "n=3"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("sidecar: ok", result.stdout)
        self.assertEqual(self.events()[0]["counts"], {"n": 3})

    def test_cli_emits_user_facing_progress_fields(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNTIME / "sidecar_events.py"),
                "platform-youtube",
                "progress",
                "sweep complete",
                "--summary",
                "18 relevant candidates",
                "--next",
                "Curate the shortlist",
                "--risk",
                "Instagram coverage is thin",
                "--eta-minutes",
                "8-12",
                "--timeout-seconds",
                "480",
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0)
        event = self.events()[0]
        self.assertEqual(event["summary"], "18 relevant candidates")
        self.assertEqual(event["next"], "Curate the shortlist")
        self.assertEqual(event["risk"], "Instagram coverage is thin")
        self.assertEqual(event["eta_minutes"], "8-12")
        self.assertEqual(event["timeout_seconds"], 480)


class RunPhaseTests(SidecarEnvironment):
    def run_phase(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(RUNTIME / "run_phase.py"), *args],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    def job(self, phase: str) -> dict:
        path = Path(self._tmp.name) / "progress" / "jobs" / f"{phase}.json"
        return json.loads(path.read_text())

    def test_foreground_success_emits_start_and_done(self) -> None:
        result = self.run_phase(
            "run", "--phase", "keywords", "--skill", "tiktok-keyword-research",
            "--", sys.executable, "-c", "print('working')",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("working", result.stdout)
        statuses = [e["status"] for e in self.events() if e["phase"] == "keywords"]
        self.assertEqual(statuses[0], "start")
        self.assertEqual(statuses[-1], "done")
        self.assertEqual(self.job("keywords")["status"], "done")

    def test_foreground_failure_emits_error(self) -> None:
        result = self.run_phase(
            "run", "--phase", "curation", "--", sys.executable, "-c", "raise SystemExit(3)",
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.job("curation")["exit"], 3)
        self.assertEqual([e["status"] for e in self.events()][-1], "error")

    def test_expected_exit_code_emits_warning_without_failing_status(self) -> None:
        result = self.run_phase(
            "run", "--phase", "platform-instagram", "--expected-exit-code", "2",
            "--", sys.executable, "-c", "print('no qualifying results'); raise SystemExit(2)",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.job("platform-instagram")["status"], "warning")
        event = self.events()[-1]
        self.assertEqual(event["status"], "warning")
        self.assertTrue(event["expected_exit"])
        status = self.run_phase("status", "--phases", "platform-instagram")
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)

    def test_foreground_timeout_stops_command_and_reports_budget(self) -> None:
        started = time.monotonic()
        result = self.run_phase(
            "run",
            "--phase",
            "strategy-pick-1",
            "--timeout-seconds",
            "0.2",
            "--",
            sys.executable,
            "-c",
            "import time; time.sleep(5)",
        )
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - started, 2)
        job = self.job("strategy-pick-1")
        self.assertTrue(job["timed_out"])
        self.assertEqual(job["timeout_seconds"], 0.2)
        event = self.events()[-1]
        self.assertTrue(event["timed_out"])
        self.assertEqual(event["timeout_seconds"], 0.2)
        self.assertIn("time limit reached", event["message"])

    def test_missing_command_reports_127(self) -> None:
        result = self.run_phase("run", "--phase", "x", "--", "definitely-not-a-command-xyz")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(self.job("x")["status"], "failed")

    def test_background_jobs_run_in_parallel_and_status_waits(self) -> None:
        script = "import time; time.sleep(1); print('done sleeping')"
        started = time.monotonic()
        for phase in ("platform-tiktok", "platform-youtube"):
            result = self.run_phase(
                "run", "--bg", "--phase", phase, "--", sys.executable, "-c", script,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("started phase=" + phase, result.stdout)
        result = self.run_phase("status", "--wait", "--interval", "0.2", "--timeout", "30")
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(elapsed, 10)
        for phase in ("platform-tiktok", "platform-youtube"):
            self.assertEqual(self.job(phase)["status"], "done")
            log = Path(self._tmp.name) / "progress" / "logs" / f"{phase}.log"
            self.assertIn("done sleeping", log.read_text())

    def test_background_expected_exit_code_propagates_to_worker(self) -> None:
        result = self.run_phase(
            "run", "--bg", "--phase", "platform-instagram",
            "--expected-exit-code", "2", "--", sys.executable, "-c",
            "print('empty fallback'); raise SystemExit(2)",
        )
        self.assertEqual(result.returncode, 0)
        status = self.run_phase(
            "status", "--wait", "--interval", "0.05", "--timeout", "5",
            "--phases", "platform-instagram",
        )
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        self.assertEqual(self.job("platform-instagram")["status"], "warning")

    def test_status_max_wait_returns_while_job_continues(self) -> None:
        script = "import time; time.sleep(1); print('slice finished')"
        result = self.run_phase(
            "run", "--bg", "--phase", "platform-youtube", "--", sys.executable, "-c", script,
        )
        self.assertEqual(result.returncode, 0)
        started = time.monotonic()
        result = self.run_phase(
            "status", "--wait", "--interval", "0.05", "--max-wait", "0.15",
            "--phases", "platform-youtube",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertIn("still running", result.stdout)
        result = self.run_phase(
            "status", "--wait", "--interval", "0.05", "--timeout", "5",
            "--phases", "platform-youtube",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_status_flags_crashed_jobs(self) -> None:
        jobs = Path(self._tmp.name) / "progress" / "jobs"
        jobs.mkdir(parents=True)
        (jobs / "ghost.json").write_text(json.dumps({"phase": "ghost", "status": "running", "pid": 99999999}))
        result = self.run_phase("status")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.job("ghost")["status"], "failed")


class DoctorTests(SidecarEnvironment):
    def test_doctor_json_reports_structured_checks(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "doctor.py"), "--json", "--skip-auth", "--skip-sessions"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        report = json.loads(result.stdout)
        names = [c["name"] for c in report["checks"]]
        self.assertEqual(names, ["python", "node", "uv", "chrome", "yt-dlp"])
        python_check = report["checks"][0]
        self.assertEqual(python_check["ok"], sys.version_info >= (3, 11))
        for check in report["checks"]:
            self.assertIn("detail", check)
            if check["ok"] is not True:
                self.assertIn("fix", check)
        phases = [e for e in self.events() if e["phase"] == "doctor"]
        self.assertEqual(phases[0]["status"], "start")
        self.assertIn(phases[-1]["status"], ("done", "need-user"))


class WorkflowPlanTests(SidecarEnvironment):
    def run_plan(self, mode: str) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNTIME / "workflow_plan.py"),
                "--mode",
                mode,
                "--subject",
                "Example",
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads((Path(self._tmp.name) / "progress" / "workflow.json").read_text())

    def test_production_plan_includes_parallel_work_and_delivery(self) -> None:
        plan = self.run_plan("production-complete")
        self.assertEqual(plan["status"], "running")
        self.assertEqual(plan["subject"], "Example")
        self.assertEqual(plan["target_minutes"], "30–45")
        self.assertEqual(plan["target_seconds"], 45 * 60)
        stages = {stage["id"]: stage for stage in plan["stages"]}
        self.assertEqual(stages["discovery"]["kind"], "parallel")
        self.assertEqual(stages["discovery"]["budget_seconds"], 720)
        self.assertEqual(len(stages["discovery"]["phases"]), 4)
        self.assertIn("delivery", stages)

    def test_fast_draft_excludes_deep_analysis_and_delivery(self) -> None:
        plan = self.run_plan("fast-draft")
        stage_ids = [stage["id"] for stage in plan["stages"]]
        self.assertNotIn("strategy", stage_ids)
        self.assertNotIn("delivery", stage_ids)
        self.assertIn("explicitly incomplete", plan["deliverable"])
        event = self.events()[-1]
        self.assertEqual(event["mode"], "fast-draft")
        self.assertEqual(event["next"], "Setup")
        self.assertEqual(event["workflow"]["mode"], "fast-draft")

    def test_workflow_can_be_marked_complete(self) -> None:
        self.run_plan("production-complete")
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "workflow_plan.py"), "--complete"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan = json.loads((Path(self._tmp.name) / "progress" / "workflow.json").read_text())
        self.assertEqual(plan["status"], "complete")
        self.assertIn("completed", plan)
        self.assertEqual(self.events()[-1]["status"], "done")

    def test_manual_stage_records_start_check_and_completion(self) -> None:
        self.run_plan("production-complete")
        for option in ("--stage-start", "--stage-check", "--stage-complete"):
            result = subprocess.run(
                [sys.executable, str(RUNTIME / "workflow_plan.py"), option, "discovery"],
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan = json.loads((Path(self._tmp.name) / "progress" / "workflow.json").read_text())
        stage = next(item for item in plan["stages"] if item["id"] == "discovery")
        self.assertEqual(stage["status"], "complete")
        self.assertIn("started", stage)
        self.assertIn("completed", stage)
        self.assertGreaterEqual(stage["elapsed_seconds"], 0)

    def test_manual_stage_check_stops_new_work_after_budget(self) -> None:
        plan = self.run_plan("production-complete")
        stage = next(item for item in plan["stages"] if item["id"] == "discovery")
        stage["started"] = "2020-01-01T00:00:00Z"
        stage["status"] = "running"
        plan["started"] = "2020-01-01T00:00:00Z"
        (Path(self._tmp.name) / "progress" / "workflow.json").write_text(json.dumps(plan))

        result = subprocess.run(
            [sys.executable, str(RUNTIME / "workflow_plan.py"), "--stage-check", "discovery"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["exhausted"])
        self.assertEqual(payload["remaining_seconds"], 0)
        self.assertEqual(payload["exhausted_by"], ["stage", "workflow"])
        self.assertIn("time budget reached", self.events()[-1]["message"])


if __name__ == "__main__":
    unittest.main()
