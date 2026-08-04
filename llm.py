"""Qwen primary / Gemini fallback LLM gateway with quota-aware failover."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")

DEFAULT_TIMEOUT = 90
MAX_RETRIES = 3
DEFAULT_MAX_TOKENS = 3000

_ENV_MTIME = None
_LAST_KEYS = {}
_CIRCUIT_OPEN_UNTIL: dict[str, float] = {}
_CIRCUIT_REASON: dict[str, str] = {}


class ProviderCallError(RuntimeError):
    """A provider error carrying enough information for safe retry routing."""

    def __init__(self, message, *, retryable=True, retry_after=None, status_code=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
        self.status_code = status_code


class LLMUnavailableError(RuntimeError):
    """Raised when every configured provider is temporarily unavailable."""

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def _read_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(_ENV_PATH):
        return values
    try:
        with open(_ENV_PATH, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
    except Exception as exc:
        print(f"[llm] .env 로드 실패(기존 설정 유지): {exc}")
    return values


def _refresh_settings(force=False):
    """Reload .env when it changes so a long-running service sees rotated keys."""
    global _ENV_MTIME
    global DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, QWEN_MODEL, QWEN_STRONG_MODEL
    global GEMINI_API_KEY, GEMINI_MODEL

    try:
        mtime = os.path.getmtime(_ENV_PATH)
    except OSError:
        mtime = None
    if not force and mtime == _ENV_MTIME:
        return

    values = _read_dotenv()

    def setting(name, default=""):
        # The project-local .env is the source of truth for the daemon. This
        # intentionally avoids stale launchd environment values after key rotation.
        return values.get(name, os.getenv(name, default)).strip()

    old_keys = dict(_LAST_KEYS)
    DASHSCOPE_API_KEY = setting("DASHSCOPE_API_KEY")
    DASHSCOPE_BASE_URL = setting(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ).rstrip("/")
    QWEN_MODEL = setting("QWEN_MODEL", "qwen3.6-flash")
    QWEN_STRONG_MODEL = setting("QWEN_STRONG_MODEL", "qwen3.7-plus")
    GEMINI_API_KEY = setting("GEMINI_API_KEY")
    GEMINI_MODEL = setting("GEMINI_MODEL", "gemini-2.5-flash")
    _LAST_KEYS.update({"QWEN": DASHSCOPE_API_KEY, "GEMINI": GEMINI_API_KEY})
    _ENV_MTIME = mtime

    for provider in ("QWEN", "GEMINI"):
        if old_keys and old_keys.get(provider) != _LAST_KEYS.get(provider):
            _CIRCUIT_OPEN_UNTIL.pop(provider, None)
            _CIRCUIT_REASON.pop(provider, None)


_refresh_settings(force=True)


def _log_usage(post_id, provider, model, prompt_tokens, completion_tokens, ok, note=""):
    if post_id is None:
        return
    try:
        from db import get_conn

        msg = (f"[LLM] {provider}/{model} in={prompt_tokens} out={completion_tokens} "
               f"{'OK' if ok else 'FAIL'} {note}").strip()
        conn = get_conn()
        conn.execute(
            "INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'LLM', ?, ?)",
            (post_id, msg, "info" if ok else "warning"),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_qwen_reset(message: str):
    match = re.search(r"reset at\s+(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\s+UTC", message, re.I)
    if not match:
        return None
    now = datetime.now(timezone.utc)
    month, day, hour, minute, second = map(int, match.groups())
    year = now.year
    try:
        candidate = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        if candidate.timestamp() < now.timestamp() - 86400:
            candidate = candidate.replace(year=year + 1)
        return candidate.timestamp()
    except ValueError:
        return None


def _call_qwen(prompt, model, max_tokens, temperature, system=None):
    import requests

    _refresh_settings()
    url = f"{DASHSCOPE_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
    if resp.status_code != 200:
        body = resp.text[:500]
        retry_after = None
        retryable = resp.status_code >= 500
        if resp.status_code == 429:
            retry_after = _parse_qwen_reset(body) or (time.time() + 900)
            retryable = False
        elif resp.status_code in (400, 401, 403, 404):
            retry_after = time.time() + (600 if resp.status_code in (401, 403) else 3600)
            retryable = False
        raise ProviderCallError(
            f"Qwen HTTP {resp.status_code}: {body}",
            retryable=retryable,
            retry_after=retry_after,
            status_code=resp.status_code,
        )
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _call_gemini(prompt, model, max_tokens, temperature, system=None):
    from google import genai

    _refresh_settings()
    client = genai.Client(api_key=GEMINI_API_KEY)
    contents = prompt if not system else f"{system}\n\n{prompt}"
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config={"max_output_tokens": max_tokens, "temperature": temperature},
    )
    text = response.text
    pt = ct = 0
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage:
            pt = getattr(usage, "prompt_token_count", 0) or 0
            ct = getattr(usage, "candidates_token_count", 0) or 0
    except Exception:
        pass
    return text, pt, ct


def _classify_error(provider: str, exc: Exception) -> ProviderCallError:
    if isinstance(exc, ProviderCallError):
        return exc
    message = str(exc)
    upper = message.upper()
    if any(token in upper for token in ("429", "RESOURCE_EXHAUSTED", "QUOTA")):
        return ProviderCallError(message, retryable=False, retry_after=time.time() + 900, status_code=429)
    if any(token in upper for token in ("401", "403", "UNAUTHENTICATED", "PERMISSION_DENIED")):
        return ProviderCallError(message, retryable=False, retry_after=time.time() + 600)
    if any(token in upper for token in ("INVALID_ARGUMENT", "NOT_FOUND", "400", "404")):
        return ProviderCallError(message, retryable=False, retry_after=time.time() + 3600)
    return ProviderCallError(message, retryable=True)


def _provider_chain(tier):
    _refresh_settings()
    qwen_model = QWEN_STRONG_MODEL if tier == "strong" else QWEN_MODEL
    chain = []
    if DASHSCOPE_API_KEY:
        chain.append(("QWEN", _call_qwen, qwen_model))
    if GEMINI_API_KEY:
        chain.append(("GEMINI", _call_gemini, GEMINI_MODEL))
    return chain


def _open_circuit(provider: str, error: ProviderCallError):
    if error.retry_after:
        _CIRCUIT_OPEN_UNTIL[provider] = max(time.time() + 5, error.retry_after)
        _CIRCUIT_REASON[provider] = str(error)[:180]


def generate(prompt, tier="cheap", max_tokens=DEFAULT_MAX_TOKENS,
             temperature=0.8, system=None, post_id=None):
    """Generate text, immediately falling back on quota/auth/client errors."""
    chain = _provider_chain(tier)
    if not chain:
        raise LLMUnavailableError(
            "사용 가능한 LLM API 키가 없습니다 (.env의 DASHSCOPE_API_KEY / GEMINI_API_KEY 확인).",
            retry_after=time.time() + 900,
        )

    last_error = None
    retry_times = []
    for idx, (name, fn, model) in enumerate(chain):
        circuit_until = _CIRCUIT_OPEN_UNTIL.get(name, 0)
        if circuit_until > time.time():
            retry_times.append(circuit_until)
            reason = _CIRCUIT_REASON.get(name, "일시적 공급자 대기")
            last_error = ProviderCallError(
                f"{name} 회로 대기: {reason}",
                retryable=False,
                retry_after=circuit_until,
            )
            continue
        _CIRCUIT_OPEN_UNTIL.pop(name, None)
        _CIRCUIT_REASON.pop(name, None)

        for attempt in range(MAX_RETRIES):
            try:
                text, prompt_tokens, completion_tokens = fn(
                    prompt, model, max_tokens, temperature, system
                )
                if not text or not text.strip():
                    raise ProviderCallError("빈 응답", retryable=True)
                _CIRCUIT_OPEN_UNTIL.pop(name, None)
                _CIRCUIT_REASON.pop(name, None)
                note = "(fallback)" if idx > 0 else ""
                _log_usage(post_id, name, model, prompt_tokens, completion_tokens, True, note)
                return text.strip()
            except Exception as exc:
                error = _classify_error(name, exc)
                last_error = error
                _log_usage(
                    post_id, name, model, 0, 0, False,
                    f"({attempt + 1}/{MAX_RETRIES}) {error}",
                )
                if not error.retryable:
                    _open_circuit(name, error)
                    if error.retry_after:
                        retry_times.append(error.retry_after)
                    break
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5 * (2 ** attempt))

    future_retries = [ts for ts in retry_times if ts > time.time()]
    retry_after = min(future_retries) if future_retries else time.time() + 900
    raise LLMUnavailableError(
        f"모든 LLM 공급자 호출 실패. 마지막 오류: {last_error}",
        retry_after=retry_after,
    )


def available_providers():
    _refresh_settings()
    now = time.time()
    out = []
    if DASHSCOPE_API_KEY:
        suffix = " [대기]" if _CIRCUIT_OPEN_UNTIL.get("QWEN", 0) > now else ""
        out.append(f"qwen({QWEN_MODEL}){suffix}")
    if GEMINI_API_KEY:
        suffix = " [대기]" if _CIRCUIT_OPEN_UNTIL.get("GEMINI", 0) > now else ""
        out.append(f"gemini({GEMINI_MODEL}){suffix}")
    return out


if __name__ == "__main__":
    print("설정된 공급자:", available_providers())
    try:
        print(generate("한 문장으로 인사말을 작성하세요.", tier="cheap", max_tokens=80))
    except Exception as exc:
        print("LLM 실패:", exc)
