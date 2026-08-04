"""One-time, no-echo setup for Naver credentials in macOS Keychain."""
import argparse
import getpass
import subprocess

from naver_auth import (
    attempt_auto_login, delete_credentials, require_manual_naver_reauth,
    store_credentials,
)


def _mac_dialog(prompt: str, hidden: bool = False) -> str:
    hidden_clause = " with hidden answer" if hidden else ""
    script = (
        f'text returned of (display dialog "{prompt}" default answer ""'
        f'{hidden_clause} buttons {{"취소", "확인"}} default button "확인" '
        'with title "Blog Agent 네이버 자동 로그인")'
    )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="네이버 자동 로그인 키체인 설정")
    parser.add_argument("--delete", action="store_true", help="저장된 자격증명 삭제")
    parser.add_argument("--gui", action="store_true", help="macOS 보안 입력 창 사용")
    args = parser.parse_args()

    if args.delete:
        delete_credentials()
        print("네이버 자동 로그인 자격증명을 키체인에서 삭제했습니다.")
        return

    if args.gui:
        naver_id = _mac_dialog("네이버 아이디를 입력하세요").strip()
        password = _mac_dialog("네이버 비밀번호를 입력하세요", hidden=True)
    else:
        naver_id = input("네이버 아이디: ").strip()
        password = getpass.getpass("네이버 비밀번호(화면에 표시되지 않음): ")
    if not naver_id or not password:
        raise SystemExit("아이디와 비밀번호가 모두 필요합니다.")
    store_credentials(naver_id, password)
    print("macOS 키체인에 저장했습니다. .env·DB·Git에는 기록되지 않습니다.")
    print("저장된 자격증명으로 세션 갱신을 확인합니다...")
    result = attempt_auto_login(headless=True)
    print(f"{'자동 로그인 성공' if result.ok else '자동 로그인 보류'}: {result.reason}")
    if not result.ok and result.manual_action_required:
        require_manual_naver_reauth(result.reason)
        print("CAPTCHA·2단계 인증이 있으면 login_naver.py로 한 번만 수동 확인하세요.")


if __name__ == "__main__":
    main()
