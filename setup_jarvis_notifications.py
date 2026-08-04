"""Import the existing Jarvis Telegram destination into macOS Keychain once."""
import argparse
from pathlib import Path

import jarvis_notify
from db import get_conn


DEFAULT_JARVIS_ENV = Path(
    "/Users/choo/.gemini/antigravity/scratch/secretary_agent/personal-agent-os/.env"
)


def _read_env(path: Path) -> dict[str, str]:
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main():
    parser = argparse.ArgumentParser(description="Jarvis Telegram 알림 연동")
    parser.add_argument("--jarvis-env", type=Path, default=DEFAULT_JARVIS_ENV)
    args = parser.parse_args()

    values = _read_env(args.jarvis_env)
    token = values.get("TELEGRAM_BOT_TOKEN", "")
    users = [x.strip() for x in values.get("ALLOWED_USER_IDS", "").split(",") if x.strip()]
    enabled = values.get("TELEGRAM_SEND_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not enabled:
        raise SystemExit("Jarvis Telegram 전송이 비활성 상태입니다.")
    if not token or len(users) != 1:
        raise SystemExit("Jarvis 토큰과 단일 허용 사용자 설정이 필요합니다.")

    jarvis_notify.store_configuration(token, users[0])
    print("Jarvis Telegram 설정을 macOS Keychain에 저장했습니다.")
    conn = get_conn()
    manual = conn.execute("""
        SELECT COUNT(*) FROM accounts
        WHERE platform = 'naver' AND status = 'manual_reauth_required'
    """).fetchone()[0] > 0
    conn.close()
    if manual:
        sent = jarvis_notify.send_state(
            "naver_auth",
            "manual_required",
            "네이버 수동 확인 필요",
            "현재 네이버 추가 보안 확인을 기다리고 있어 생성·발행이 안전 정지된 상태입니다.",
            severity="warning",
            force=True,
        )
    else:
        sent = jarvis_notify.send_test()
    print("Jarvis 알림 전송:", "성공" if sent else "실패")


if __name__ == "__main__":
    main()
