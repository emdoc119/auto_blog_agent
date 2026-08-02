import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import llm
import pipeline_state
from agents import orchestrator, writer


class LLMRoutingTests(unittest.TestCase):
    def setUp(self):
        llm._CIRCUIT_OPEN_UNTIL.clear()
        llm._CIRCUIT_REASON.clear()

    def test_non_retryable_quota_error_falls_back_immediately(self):
        calls = []

        def qwen(*_args):
            calls.append("qwen")
            raise llm.ProviderCallError(
                "quota", retryable=False, retry_after=time.time() + 600, status_code=429
            )

        def gemini(*_args):
            calls.append("gemini")
            return "ok", 1, 1

        with patch.object(
            llm,
            "_provider_chain",
            return_value=[("QWEN", qwen, "q"), ("GEMINI", gemini, "g")],
        ):
            self.assertEqual(llm.generate("hello"), "ok")
            self.assertEqual(calls, ["qwen", "gemini"])

            calls.clear()
            self.assertEqual(llm.generate("hello again"), "ok")
            self.assertEqual(calls, ["gemini"])

    def test_qwen_reset_timestamp_is_parsed(self):
        reset = llm._parse_qwen_reset("quota will reset at 08-05 06:12:00 UTC")
        self.assertIsNotNone(reset)
        self.assertGreater(reset, time.time())


class RetryPolicyTests(unittest.TestCase):
    def test_defer_post_records_provider_retry_time(self):
        class FakeCursor:
            values = None

            def execute(self, sql, values=()):
                if sql.lstrip().startswith("SELECT"):
                    return self
                self.values = values
                return self

            def fetchone(self):
                return {"retry_count": 1}

            def commit(self):
                pass

            def close(self):
                pass

        class TemporaryError(Exception):
            retry_after = time.time() + 120

        conn = FakeCursor()
        with patch.object(pipeline_state, "get_conn", return_value=conn):
            attempt, retry_at = pipeline_state.defer_post(42, TemporaryError("temporary"))

        self.assertEqual(attempt, 2)
        self.assertEqual(conn.values[0], 2)
        self.assertEqual(conn.values[1], retry_at)
        self.assertEqual(conn.values[3], 42)


class PipelineStateTransitionTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE projects (id INTEGER PRIMARY KEY, strategy_feedback TEXT);
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, content TEXT,
                status TEXT, seo_tags TEXT, retry_count INTEGER DEFAULT 0,
                retry_after DATETIME, last_error TEXT
            );
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, agent TEXT,
                message TEXT, level TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO projects VALUES (1, 'strategy');
            INSERT INTO posts (id, project_id, status) VALUES (1, 1, 'writing');
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_writer_keeps_draft_unpublishable_until_pipeline_finishes(self):
        draft = "TITLE: 안전한 초안\n---\n" + ("충분한 본문입니다. " * 80)
        with patch.object(writer, "get_conn", side_effect=self._connect), \
             patch.object(writer.llm, "generate", return_value=draft), \
             patch.object(writer, "insert_photos", side_effect=lambda content, _keywords: content):
            writer.write(1, "테스트", "자료")
        conn = self._connect()
        status = conn.execute("SELECT status FROM posts WHERE id=1").fetchone()[0]
        conn.close()
        self.assertEqual(status, "editing")

    def test_orchestrator_marks_scheduled_only_at_the_end(self):
        with patch.object(orchestrator, "get_conn", side_effect=self._connect), \
             patch.object(orchestrator.researcher, "research", return_value="research"), \
             patch.object(orchestrator.writer, "write", return_value=("title", "content")), \
             patch.object(orchestrator, "ENABLE_QUALITY_SCORE", False), \
             patch.object(orchestrator, "ENABLE_EDITOR", False), \
             patch.object(orchestrator, "ENABLE_SEO", False), \
             patch.object(orchestrator, "AUTO_PUBLISH", True):
            orchestrator.run_pipeline(1, ["테스트"])
        conn = self._connect()
        status = conn.execute("SELECT status FROM posts WHERE id=1").fetchone()[0]
        conn.close()
        self.assertEqual(status, "scheduled")


if __name__ == "__main__":
    unittest.main()
