"""State-transition alerts sent through the existing Jarvis Telegram bot."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import requests

from db import get_conn
from naver_auth import _keychain_read, _keychain_write


TOKEN_SERVICE = "blog-agent-jarvis-telegram-token"
USER_SERVICE = "blog-agent-jarvis-user-id"
REMINDER_HOURS = 12


def store_configuration(bot_token: str, user_id: str) -> None:
    if not bot_token or not user_id or not str(user_id).isdigit():
        raise ValueError("Jarvis Telegram 설정이 올바르지 않습니다.")
    _keychain_write(TOKEN_SERVICE, bot_token)
    _keychain_write(USER_SERVICE, str(user_id))


def configuration_available() -> bool:
    return bool(_keychain_read(TOKEN_SERVICE) and _keychain_read(USER_SERVICE))


def _should_send(event_key: str, state: str, force: bool = False) -> bool:
    if force:
        return True
    conn = get_conn()
    row = conn.execute(
        "SELECT state, last_sent_at FROM notification_state WHERE event_key = ?",
        (event_key,),
    ).fetchone()
    conn.close()
    if not row or row["state"] != state or not row["last_sent_at"]:
        return True
    try:
        last_sent = datetime.fromisoformat(row["last_sent_at"])
        return datetime.now() - last_sent >= timedelta(hours=REMINDER_HOURS)
    except (TypeError, ValueError):
        return True


def _record_sent(event_key: str, state: str, payload: str) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO notification_state (event_key, state, last_sent_at, payload_hash)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(event_key) DO UPDATE SET
            state = excluded.state,
            last_sent_at = excluded.last_sent_at,
            payload_hash = excluded.payload_hash
        """,
        (
            event_key,
            state,
            datetime.now().isoformat(timespec="seconds"),
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        ),
    )
    conn.commit()
    conn.close()


def send_state(
    event_key: str,
    state: str,
    title: str,
    message: str,
    *,
    severity: str = "warning",
    force: bool = False,
) -> bool:
    """Send one-user Jarvis alert, deduplicated by event state."""
    try:
        if not _should_send(event_key, state, force=force):
            return False
    except Exception:
        return False

    token = _keychain_read(TOKEN_SERVICE)
    user_id = _keychain_read(USER_SERVICE)
    if not token or not user_id or not user_id.isdigit():
        return False

    icon = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "resolved": "✅"}.get(
        severity, "🔔"
    )
    payload = (
        f"{icon} [Jarvis · Blog Agent] {title}\n\n"
        f"{message[:3200]}\n\n"
        f"상태: {state}\n시각: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}"
    )
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": int(user_id), "text": payload},
            timeout=15,
        )
        if response.status_code != 200:
            return False
        body = response.json()
        if not body.get("ok"):
            return False
        _record_sent(event_key, state, payload)
        return True
    except Exception:
        # Notification failures must never break generation/auth recovery.
        return False


def send_test() -> bool:
    return send_state(
        "jarvis_blog_integration",
        "configured",
        "블로그 알림 연동 완료",
        "수동 확인 필요, 자동화 중단, 정상 복구 상태를 이 채널로 알려드립니다.",
        severity="info",
        force=True,
    )
