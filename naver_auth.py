"""Naver session maintenance with credentials stored in macOS Keychain.

Passwords are never read from .env, logged, or stored in SQLite.  The saved
Playwright session remains the primary path; credentials are used only when
that session has expired.
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "naver_state.json")
LOGIN_URL = "https://nid.naver.com/nidlogin.login"
WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"
BLOG_HOME = "https://section.blog.naver.com/BlogHome.naver"

KEYCHAIN_ACCOUNT = "blog-agent"
KEYCHAIN_ID_SERVICE = "blog-agent-naver-id"
KEYCHAIN_PASSWORD_SERVICE = "blog-agent-naver-password"
LOCK_FILE = "/tmp/blog-agent-naver-auth.lock"

_SECURITY = None
_CORE_FOUNDATION = None


def _frameworks():
    """Load Keychain Services directly so secrets never appear in argv."""
    global _SECURITY, _CORE_FOUNDATION
    if _SECURITY is not None:
        return _SECURITY, _CORE_FOUNDATION

    security = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/Security.framework/Security"
    )
    core = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainFindGenericPassword.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
    ]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
    security.SecKeychainItemDelete.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    core.CFRelease.argtypes = [ctypes.c_void_p]

    _SECURITY, _CORE_FOUNDATION = security, core
    return security, core


@dataclass
class AuthResult:
    ok: bool
    reason: str
    manual_action_required: bool = False


def _keychain_read(service: str) -> str:
    security, core = _frameworks()
    service_bytes = service.encode("utf-8")
    account_bytes = KEYCHAIN_ACCOUNT.encode("utf-8")
    length = ctypes.c_uint32()
    data = ctypes.c_void_p()
    item = ctypes.c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service_bytes), service_bytes,
        len(account_bytes), account_bytes,
        ctypes.byref(length), ctypes.byref(data), ctypes.byref(item),
    )
    try:
        if status != 0 or not data.value:
            return ""
        return ctypes.string_at(data, length.value).decode("utf-8")
    finally:
        if data.value:
            security.SecKeychainItemFreeContent(None, data)
        if item.value:
            core.CFRelease(item)


def _keychain_write(service: str, value: str) -> None:
    if not value:
        raise ValueError("빈 자격증명은 저장할 수 없습니다.")
    security, core = _frameworks()
    service_bytes = service.encode("utf-8")
    account_bytes = KEYCHAIN_ACCOUNT.encode("utf-8")
    value_bytes = value.encode("utf-8")
    item = ctypes.c_void_p()
    find_status = security.SecKeychainFindGenericPassword(
        None,
        len(service_bytes), service_bytes,
        len(account_bytes), account_bytes,
        None, None, ctypes.byref(item),
    )
    try:
        if find_status == 0 and item.value:
            status = security.SecKeychainItemModifyAttributesAndData(
                item, None, len(value_bytes), value_bytes
            )
        else:
            new_item = ctypes.c_void_p()
            status = security.SecKeychainAddGenericPassword(
                None,
                len(service_bytes), service_bytes,
                len(account_bytes), account_bytes,
                len(value_bytes), value_bytes,
                ctypes.byref(new_item),
            )
            if new_item.value:
                core.CFRelease(new_item)
    finally:
        if item.value:
            core.CFRelease(item)
    if status != 0:
        raise RuntimeError("macOS 키체인 저장에 실패했습니다.")


def store_credentials(naver_id: str, password: str) -> None:
    """Store credentials in Keychain. Values are deliberately never returned."""
    _keychain_write(KEYCHAIN_ID_SERVICE, naver_id.strip())
    _keychain_write(KEYCHAIN_PASSWORD_SERVICE, password)


def delete_credentials() -> None:
    security, core = _frameworks()
    account_bytes = KEYCHAIN_ACCOUNT.encode("utf-8")
    for service in (KEYCHAIN_ID_SERVICE, KEYCHAIN_PASSWORD_SERVICE):
        service_bytes = service.encode("utf-8")
        item = ctypes.c_void_p()
        status = security.SecKeychainFindGenericPassword(
            None,
            len(service_bytes), service_bytes,
            len(account_bytes), account_bytes,
            None, None, ctypes.byref(item),
        )
        try:
            if status == 0 and item.value:
                security.SecKeychainItemDelete(item)
        finally:
            if item.value:
                core.CFRelease(item)


def get_credentials() -> Optional[Tuple[str, str]]:
    naver_id = _keychain_read(KEYCHAIN_ID_SERVICE)
    password = _keychain_read(KEYCHAIN_PASSWORD_SERVICE)
    if not naver_id or not password:
        return None
    return naver_id, password


def credentials_available() -> bool:
    return get_credentials() is not None


def activate_naver_accounts() -> None:
    from db import get_conn

    conn = get_conn()
    conn.execute("UPDATE accounts SET status = 'active' WHERE platform = 'naver'")
    conn.commit()
    conn.close()


def require_manual_naver_reauth() -> None:
    """Stop automatic retries after a security challenge or missing setup."""
    from db import get_conn

    conn = get_conn()
    conn.execute(
        "UPDATE accounts SET status = 'manual_reauth_required' WHERE platform = 'naver'"
    )
    conn.commit()
    conn.close()


def _has_naver_session(context) -> bool:
    return any(cookie.get("name") == "NID_SES" for cookie in context.cookies())


def _write_access_valid(context) -> bool:
    page = context.new_page()
    try:
        page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)
        if "nidlogin" in page.url.lower():
            return False
        if not _has_naver_session(context):
            return False
        return "GoBlogWrite" not in page.url or any(
            "PostWriteForm" in frame.url for frame in page.frames
        )
    except Exception:
        return False
    finally:
        page.close()


def _challenge_reason(page) -> Optional[str]:
    try:
        text = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        text = ""
    checks = (
        ("captcha", "CAPTCHA 보안 확인"),
        ("자동입력 방지", "자동입력 방지 확인"),
        ("추가 확인", "네이버 보안 추가 확인"),
        ("2단계 인증", "2단계 인증"),
        ("새로운 환경", "새 환경 로그인 확인"),
        ("보호조치", "계정 보호조치"),
        ("본인확인", "본인 확인"),
    )
    for marker, reason in checks:
        if marker in text:
            return reason
    return None


def _fill_login(page, naver_id: str, password: str) -> None:
    id_input = page.locator("#id").first
    pw_input = page.locator("#pw").first
    if id_input.count() == 0 or pw_input.count() == 0:
        raise RuntimeError("네이버 로그인 입력창을 찾지 못했습니다.")

    id_input.click()
    page.keyboard.press("Meta+a")
    page.keyboard.type(naver_id, delay=35)
    pw_input.click()
    page.keyboard.press("Meta+a")
    page.keyboard.type(password, delay=35)

    buttons = page.locator("button.btn_login, button:has-text('로그인')")
    login_button = None
    for index in range(buttons.count()):
        candidate = buttons.nth(index)
        if candidate.is_visible() and candidate.is_enabled():
            login_button = candidate
            break
    if login_button is None:
        raise RuntimeError("네이버 로그인 버튼을 찾지 못했습니다.")
    login_button.click(timeout=10000)


def attempt_auto_login(headless: bool = True) -> AuthResult:
    """Refresh naver_state.json, stopping cleanly on CAPTCHA or 2FA."""
    credentials = get_credentials()
    if not credentials:
        return AuthResult(False, "키체인 자격증명 없음", manual_action_required=True)

    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return AuthResult(False, "자동 로그인 이미 진행 중")

        naver_id, password = credentials
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=headless)
                context_kwargs = {"viewport": {"width": 1280, "height": 900}}
                if os.path.exists(STATE_FILE):
                    context_kwargs["storage_state"] = STATE_FILE
                context = browser.new_context(**context_kwargs)

                if _write_access_valid(context):
                    context.storage_state(path=STATE_FILE)
                    activate_naver_accounts()
                    browser.close()
                    return AuthResult(True, "기존 세션 유효")

                page = context.new_page()
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45000)
                _fill_login(page, naver_id, password)

                deadline = time.time() + 45
                challenge = None
                while time.time() < deadline:
                    time.sleep(2)
                    if _has_naver_session(context) and _write_access_valid(context):
                        try:
                            page.goto(BLOG_HOME, wait_until="domcontentloaded", timeout=30000)
                        except Exception:
                            pass
                        context.storage_state(path=STATE_FILE)
                        activate_naver_accounts()
                        browser.close()
                        return AuthResult(True, "자동 로그인 성공")
                    challenge = _challenge_reason(page)
                    if challenge:
                        break

                browser.close()
                if challenge:
                    return AuthResult(False, challenge, manual_action_required=True)
                return AuthResult(False, "로그인 완료 신호 없음", manual_action_required=True)
        except Exception as exc:
            return AuthResult(False, f"자동 로그인 오류: {str(exc)[:180]}")


def main():
    parser = argparse.ArgumentParser(description="Naver automatic session refresher")
    parser.add_argument("--headed", action="store_true", help="브라우저 창을 표시")
    args = parser.parse_args()
    result = attempt_auto_login(headless=not args.headed)
    print(f"{'SUCCESS' if result.ok else 'FAILED'}: {result.reason}")
    raise SystemExit(0 if result.ok else 2)


if __name__ == "__main__":
    main()
