"""
네이버 로그인 세션 캡처

브라우저 창을 띄워 사용자가 직접 네이버에 로그인하면,
로그인 성공을 자동 감지해 naver_state.json 을 저장합니다.

사용법:  ../venv/bin/python login_naver.py
"""
import os
import time
from playwright.sync_api import sync_playwright

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naver_state.json")
BLOG_HOME = "https://section.blog.naver.com/BlogHome.naver"
MAX_WAIT_SEC = 600  # 최대 10분 대기


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 화면에 보이는 브라우저
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")

        credentials_prefilled = False
        try:
            from naver_auth import _fill_login, get_credentials
            credentials = get_credentials()
            if credentials:
                _fill_login(page, credentials[0], credentials[1])
                credentials_prefilled = True
        except Exception as exc:
            print(f"  키체인 자동 입력 경고: {exc}")

        print("=" * 56)
        if credentials_prefilled:
            print("  키체인 정보는 자동 입력했습니다. 네이버의 추가 보안 확인만 완료하세요.")
        else:
            print("  열린 브라우저 창에서 네이버 아이디/비밀번호로 로그인하세요.")
        print("  로그인에 성공하면 자동으로 세션이 저장됩니다 (최대 10분).")
        print("=" * 56, flush=True)

        start = time.time()
        logged_in = False
        while time.time() - start < MAX_WAIT_SEC:
            time.sleep(5)
            cookies = context.cookies()
            has_session = any(c["name"] == "NID_SES" for c in cookies)
            if not has_session:
                continue
            # 로그인 확정 검증: 로그인 필수 페이지(에디터)가 로그인으로 리다이렉트되지 않는지
            check = context.new_page()
            try:
                check.goto("https://blog.naver.com/GoBlogWrite.naver", timeout=30000)
                time.sleep(3)
                if "nidlogin" not in check.url:
                    logged_in = True
            except Exception as e:
                print("  검증 중 경고:", e)
            finally:
                check.close()
            if logged_in:
                break

        if not logged_in:
            print("시간 초과: 로그인이 감지되지 않았습니다. 다시 실행해 주세요.")
            browser.close()
            return

        # 쿠키를 확정한 뒤 저장
        try:
            page.goto(BLOG_HOME, timeout=30000)
            time.sleep(3)
        except Exception:
            pass
        context.storage_state(path=STATE_FILE)
        # 재로그인 대기 때문에 멈춰 둔 네이버 계정을 즉시 재활성화합니다.
        try:
            from naver_auth import activate_naver_accounts
            activate_naver_accounts()
        except Exception as exc:
            print(f"계정 상태 재활성화 경고: {exc}")
        print(f"로그인 세션 저장 완료: {STATE_FILE}")
        browser.close()


if __name__ == "__main__":
    main()
