"""재시도 폭주 수정 회귀 테스트: 원자적 선점, 진행 중 가드, 백오프 성장."""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import db as db_module
import pipeline_state


def _connect(path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


class SchedulerClaimTests(unittest.TestCase):
    def setUp(self):
        pipeline_state._ACTIVE_PIPELINE_POSTS.clear()
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = _connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY, platform TEXT, status TEXT DEFAULT 'active'
            );
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY, account_id INTEGER, keywords TEXT,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY, project_id INTEGER, status TEXT,
                retry_count INTEGER DEFAULT 0, retry_after DATETIME,
                last_error TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO accounts VALUES (1, 'naver', 'active');
            INSERT INTO projects VALUES (1, 1, '테스트키워드', 'active');
            """
        )
        conn.commit()
        conn.close()
        self._db_patch = patch.object(db_module, "DB_PATH", self.db_path)
        self._db_patch.start()

    def tearDown(self):
        self._db_patch.stop()
        pipeline_state._ACTIVE_PIPELINE_POSTS.clear()
        os.unlink(self.db_path)

    def _connect(self):
        return _connect(self.db_path)

    def _add_post(self, post_id, status="pending", retry_after=None):
        conn = self._connect()
        conn.execute(
            "INSERT INTO posts (id, project_id, status, retry_after) VALUES (?, 1, ?, ?)",
            (post_id, status, retry_after),
        )
        conn.commit()
        conn.close()

    def _status(self, post_id):
        conn = self._connect()
        row = conn.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
        conn.close()
        return row["status"] if row else None

    def _claim(self, now=None):
        now = now or datetime.now()
        return pipeline_state.claim_pending_post(now.strftime("%Y-%m-%d %H:%M:%S"))

    def test_due_post_is_claimed_and_marked_researching(self):
        self._add_post(1)
        claimed = self._claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], 1)
        self.assertEqual(self._status(1), "researching")

    def test_backoff_post_is_not_claimed_until_due(self):
        future = (datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        self._add_post(1, retry_after=future)
        self.assertIsNone(self._claim())
        self.assertEqual(self._status(1), "pending")

    def test_inactive_account_blocks_claim(self):
        self._add_post(1)
        conn = self._connect()
        conn.execute("UPDATE accounts SET status = 'manual_reauth_required' WHERE id = 1")
        conn.commit()
        conn.close()
        self.assertIsNone(self._claim())
        self.assertEqual(self._status(1), "pending")

    def test_active_post_is_not_reclaimed_until_released(self):
        self._add_post(1)
        self.assertIsNotNone(self._claim())
        # 실패 후 defer가 pending으로 되돌려도 스레드가 살아 있으면 재선점 금지.
        conn = self._connect()
        conn.execute("UPDATE posts SET status = 'pending', retry_after = NULL WHERE id = 1")
        conn.commit()
        conn.close()
        self.assertIsNone(self._claim())
        pipeline_state.release_pipeline(1)
        reclaimed = self._claim()
        self.assertIsNotNone(reclaimed)
        self.assertEqual(reclaimed["id"], 1)

    def test_concurrent_claims_never_pick_the_same_post_twice(self):
        for post_id in range(1, 9):
            self._add_post(post_id)
        claimed_ids = []
        lock = threading.Lock()

        def worker():
            while True:
                row = self._claim()
                if row is None:
                    return
                with lock:
                    claimed_ids.append(row["id"])

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(claimed_ids), len(set(claimed_ids)))
        self.assertEqual(sorted(claimed_ids), list(range(1, 9)))


class DeferBackoffTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = _connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY, status TEXT,
                retry_count INTEGER DEFAULT 0, retry_after DATETIME, last_error TEXT
            );
            INSERT INTO posts (id, status) VALUES (1, 'researching');
            """
        )
        conn.commit()
        conn.close()
        self._db_patch = patch.object(db_module, "DB_PATH", self.db_path)
        self._db_patch.start()

    def tearDown(self):
        self._db_patch.stop()
        os.unlink(self.db_path)

    def _defer(self, error):
        return pipeline_state.defer_post(1, error)

    def _read_retry(self):
        conn = _connect(self.db_path)
        row = conn.execute("SELECT retry_count, retry_after FROM posts WHERE id = 1").fetchone()
        conn.close()
        return row["retry_count"], datetime.strptime(row["retry_after"], "%Y-%m-%d %H:%M:%S")

    def test_backoff_grows_despite_short_provider_hint(self):
        class ShortHint(Exception):
            retry_after = time.time() + 60

        retry_times = []
        for _ in range(3):
            self._defer(ShortHint("temporary"))
            _count, retry_at = self._read_retry()
            retry_times.append(retry_at)

        # 1/2/3회차 지수 백오프(15/30/60분)가 1분 제공자 힌트보다 우선해야 함.
        self.assertTrue(retry_times[0] < retry_times[1] < retry_times[2])
        self.assertGreaterEqual(retry_times[2], datetime.now() + timedelta(minutes=55))

    def test_provider_reset_later_than_backoff_is_respected(self):
        class ResetHint(Exception):
            retry_after = time.time() + 24 * 3600

        self._defer(ResetHint("quota reset"))
        _count, retry_at = self._read_retry()
        # 제공자 리셋 시각이 더 늦으면 그 시각을 존중해야 함.
        self.assertGreaterEqual(retry_at, datetime.now() + timedelta(hours=23, minutes=50))


if __name__ == "__main__":
    unittest.main()
