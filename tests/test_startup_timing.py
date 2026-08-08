import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from bluedot_agent.startup_timing import StartupTimer


class StartupTimerTest(unittest.TestCase):
    def test_log_records_stages_with_elapsed_launcher_time(self):
        readings = iter([10.125, 11.5])
        fixed_time = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "startup.log"
            timer = StartupTimer(
                path=path,
                started_at=10.0,
                elapsed_offset_ms=250.0,
                clock=lambda: next(readings),
                wall_clock=lambda: fixed_time,
            )
            timer.mark("cli_ready")
            timer.mark("firefox_ready", detail="ready")

            entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(
            [entry["stage"] for entry in entries],
            ["process_started", "cli_ready", "firefox_ready"],
        )
        self.assertEqual([entry["elapsed_ms"] for entry in entries], [0, 375, 1750])
        self.assertEqual(entries[1]["timestamp"], "2026-08-03T12:00:00+00:00")
        self.assertEqual(entries[0]["run_id"], entries[2]["run_id"])
        self.assertNotIn("detail", entries[1])
        self.assertEqual(entries[2]["detail"], "ready")


if __name__ == "__main__":
    unittest.main()
