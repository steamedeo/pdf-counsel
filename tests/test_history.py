import json
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import history


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp_path = Path(__file__).parent / ".tmp_history"
        shutil.rmtree(self.tmp_path, ignore_errors=True)
        self.tmp_path.mkdir()
        self.original_dir = history.HISTORY_DIR
        self.original_file = history.HISTORY_FILE
        history.HISTORY_DIR = self.tmp_path
        history.HISTORY_FILE = history.HISTORY_DIR / "chat.json"

    def tearDown(self):
        history.HISTORY_DIR = self.original_dir
        history.HISTORY_FILE = self.original_file
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def test_save_appends_message_with_id_and_timestamp(self):
        message = history.save_message("user", "hello", [])

        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"], "hello")
        self.assertTrue(message["id"])
        self.assertTrue(message["created_at"])
        self.assertEqual(history.list_messages(), [message])

    def test_loading_prunes_messages_older_than_30_days(self):
        old = {
            "id": "old",
            "role": "user",
            "content": "old",
            "citations": [],
            "created_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        }
        fresh = {
            "id": "fresh",
            "role": "assistant",
            "content": "fresh",
            "citations": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        history.HISTORY_DIR.mkdir(exist_ok=True)
        history.HISTORY_FILE.write_text(
            json.dumps({"messages": [old, fresh]}),
            encoding="utf-8",
        )

        self.assertEqual(history.list_messages(), [fresh])

    def test_clear_removes_history_file(self):
        history.save_message("user", "hello", [])

        history.clear_messages()

        self.assertFalse(history.HISTORY_FILE.exists())
        self.assertEqual(history.list_messages(), [])

    def test_malformed_history_returns_empty(self):
        history.HISTORY_DIR.mkdir(exist_ok=True)
        history.HISTORY_FILE.write_text("{not json", encoding="utf-8")

        self.assertEqual(history.list_messages(), [])


if __name__ == "__main__":
    unittest.main()
