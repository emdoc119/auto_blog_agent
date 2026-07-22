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

        print("=" * 56)
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
            # 로그인 확정 검증: 블로그 홈이 로그인 페이지로 리다이렉트되지 않는지
            check = context.new_page()
            try:
                check.goto(BLOG_HOME, timeout=30000)
                time.sleep(2)
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
        print(f"로그인 세션 저장 완료: {STATE_FILE}")
        browser.close()


if __name__ == "__main__":
    main()
