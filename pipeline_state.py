"""Shared, bounded retry state for generation and publishing pipelines."""
import threading
from datetime import datetime, timedelta

from db import get_conn

# 스케줄러가 동시에 돌릴 파이프라인 스레드 상한.
MAX_CONCURRENT_PIPELINES = 2

_CLAIM_LOCK = threading.Lock()
_ACTIVE_PIPELINE_POSTS = set()


def active_pipeline_count() -> int:
    with _CLAIM_LOCK:
        return len(_ACTIVE_PIPELINE_POSTS)


def release_pipeline(post_id: int):
    """파이프라인 스레드가 끝나면 선점했던 post의 슬롯을 해제합니다."""
    with _CLAIM_LOCK:
        _ACTIVE_PIPELINE_POSTS.discard(post_id)


def claim_pending_post(now_str: str):
    """재시도 기한이 된 다음 pending 포스트를 원자적으로 선점합니다.

    선점하면 Row(id, project_id)를, 선점할 것이 없으면 None을 반환합니다.
    조건부 UPDATE로 상태를 즉시 'researching'으로 바꿔 두 스케줄러 패스나
    스레드가 같은 포스트를 동시에 집는 것을 막고, 이 프로세스에서 이미
    처리 중인 포스트는 건너뜁니다.
    """
    with _CLAIM_LOCK:
        conn = get_conn()
        try:
            candidates = conn.execute(
                """
                SELECT p.id, p.project_id
                FROM posts p
                JOIN projects pr ON p.project_id = pr.id
                JOIN accounts a ON pr.account_id = a.id
                WHERE p.status = 'pending'
                  AND (p.retry_after IS NULL OR p.retry_after <= ?)
                  AND pr.status = 'active'
                  AND a.status = 'active'
                ORDER BY COALESCE(p.retry_after, p.created_at), p.id
                LIMIT 5
                """,
                (now_str,),
            ).fetchall()
            for row in candidates:
                post_id = row["id"]
                if post_id in _ACTIVE_PIPELINE_POSTS:
                    continue
                cur = conn.execute(
                    """
                    UPDATE posts
                    SET status = 'researching'
                    WHERE id = ?
                      AND status = 'pending'
                      AND (retry_after IS NULL OR retry_after <= ?)
                    """,
                    (post_id, now_str),
                )
                conn.commit()
                if cur.rowcount == 1:
                    _ACTIVE_PIPELINE_POSTS.add(post_id)
                    return row
            return None
        finally:
            conn.close()


def defer_post(post_id: int, error: Exception, *, base_minutes=15, max_minutes=360):
    """Return a failed post to pending with exponential/provider-aware backoff."""
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(retry_count, 0) AS retry_count FROM posts WHERE id = ?",
        (post_id,),
    ).fetchone()
    attempt = (row["retry_count"] if row else 0) + 1
    delay_minutes = min(max_minutes, base_minutes * (2 ** min(attempt - 1, 5)))
    retry_at = datetime.now() + timedelta(minutes=delay_minutes)

    provider_retry = getattr(error, "retry_after", None)
    if provider_retry:
        try:
            provider_at = datetime.fromtimestamp(float(provider_retry))
            # 제공자 요청 시각보다 일찍 재시도하지 않되, 지수 백오프보다
            # 빠르게도 재시도하지 않습니다. 짧은 제공자 힌트만 믿으면 반복
            # 실패하는 포스트가 촘촘한 재시도 루프에 갇힐 수 있습니다.
            retry_at = max(retry_at, provider_at)
        except (TypeError, ValueError, OSError, OverflowError):
            pass

    retry_text = retry_at.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE posts
        SET status = 'pending', retry_count = ?, retry_after = ?, last_error = ?
        WHERE id = ?
        """,
        (attempt, retry_text, str(error)[:1000], post_id),
    )
    conn.commit()
    conn.close()
    return attempt, retry_text


def clear_retry(post_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE posts SET retry_count = 0, retry_after = NULL, last_error = NULL WHERE id = ?",
        (post_id,),
    )
    conn.commit()
    conn.close()
