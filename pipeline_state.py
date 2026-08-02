"""Shared, bounded retry state for generation and publishing pipelines."""
from datetime import datetime, timedelta

from db import get_conn


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
            retry_at = datetime.fromtimestamp(float(provider_retry))
        except (TypeError, ValueError, OSError):
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
