import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from bluedot_agent.downloads import (
    DownloadManager,
    available_download_path,
    default_download_directory,
    open_path,
)


class FakeDownload:
    def __init__(self, filename, content=b"audio", delay=0):
        self.suggested_filename = filename
        self.content = content
        self.delay = delay

    async def save_as(self, target):
        await asyncio.sleep(self.delay)
        Path(target).write_bytes(self.content)


class FakePage:
    def __init__(self):
        self.notifications = []

    async def evaluate(self, script, payload):
        self.notifications.append(payload)


class DownloadManagerTest(unittest.IsolatedAsyncioTestCase):
    def test_default_download_directory_uses_windows_known_folder(self):
        with patch.dict(os.environ, {}, clear=True):
            path = default_download_directory(
                platform="win32",
                windows_folder=lambda: r"D:\Downloads",
            )

        self.assertEqual(path, Path(r"D:\Downloads"))

    def test_download_directory_environment_override_wins(self):
        with patch.dict(
            os.environ,
            {"BLUEDOT_DOWNLOAD_DIR": r"E:\Blue Dot"},
            clear=True,
        ):
            path = default_download_directory()

        self.assertEqual(path, Path(r"E:\Blue Dot"))

    async def test_drain_waits_for_pending_download(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = DownloadManager(Path(directory))
            manager.queue(FakeDownload("track.wav", delay=0.02))
            await manager.drain()
            self.assertEqual((Path(directory) / "track.wav").read_bytes(), b"audio")

    async def test_concurrent_duplicate_names_are_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = DownloadManager(Path(directory))
            manager.queue(FakeDownload("track.wav", b"one", delay=0.02))
            manager.queue(FakeDownload("track.wav", b"two", delay=0.01))
            await manager.drain()
            self.assertEqual(
                {path.name for path in Path(directory).iterdir()},
                {"track.wav", "track (1).wav"},
            )

    async def test_pythonw_without_stdout_does_not_turn_success_into_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = DownloadManager(Path(directory))
            with patch("sys.stdout", None):
                manager.queue(FakeDownload("track.wav"))
                await manager.drain()

            self.assertEqual(manager.errors, [])
            self.assertTrue((Path(directory) / "track.wav").exists())

    async def test_download_reports_visible_status_and_writes_event_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = FakePage()
            manager = DownloadManager(root, log_path=root / "downloads.log")
            manager.queue(FakeDownload("track.wav"), page=page)
            await manager.drain()

            entries = [
                json.loads(line)
                for line in (root / "downloads.log").read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual([entry["stage"] for entry in entries], ["queued", "saved"])
            self.assertEqual(
                page.notifications,
                [
                    {
                        "kind": "loading",
                        "text": f"Скачивание началось: track.wav → {root}",
                    },
                    {
                        "kind": "success",
                        "text": f"Скачано: {root / 'track.wav'}",
                        "can_open": True,
                    },
                ],
            )

    def test_available_path_discards_parent_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = available_download_path(Path(directory), "../unsafe/track.wav")
            self.assertEqual(path, Path(directory) / "track.wav")

    def test_available_path_skips_names_already_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "track.wav").touch()
            (root / "track (1).wav").touch()

            path = available_download_path(root, "track.wav")

            self.assertEqual(path, root / "track (2).wav")

    def test_macos_opens_download_with_system_open(self):
        with (
            patch("sys.platform", "darwin"),
            patch("bluedot_agent.downloads.subprocess.Popen") as popen,
        ):
            open_path(PurePosixPath("/tmp/track.wav"))

        popen.assert_called_once_with(["open", "/tmp/track.wav"])


if __name__ == "__main__":
    unittest.main()
