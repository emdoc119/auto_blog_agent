"""
통합 LLM 레이어 (Unified LLM Layer)

모든 에이전트(writer / trend_agent / feedback / app)가 이 모듈의 generate()만 호출합니다.

설계 목표
- 1순위: Alibaba Qwen (DashScope International, OpenAI-호환 API). 싸고 빨라서 대량 생성용.
- 2순위(폴백): Google Gemini. Qwen이 막히거나 부족할 때 보조.
- 공급자별 자동 재시도/백오프, 타임아웃, 키가 없으면 우아하게 건너뜀.
- 새 의존성 없음: Qwen은 이미 설치된 requests로 OpenAI-호환 엔드포인트를 직접 호출.

환경변수(.env)
- DASHSCOPE_API_KEY   : Qwen API 키 (sk-...)
- DASHSCOPE_BASE_URL  : 기본 https://dashscope-intl.aliyuncs.com/compatible-mode/v1
- QWEN_MODEL          : 기본(저렴) 모델. 기본값 qwen-flash
- QWEN_STRONG_MODEL   : 고품질 윤색용 모델. 기본값 qwen-plus
- GEMINI_API_KEY      : Gemini API 키
- GEMINI_MODEL        : 기본값 gemini-2.5-flash
"""
import os
import time

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """python-dotenv 의존성 없이 .env를 최소 파싱해 os.environ에 채운다."""
    env_path = os.path.join(_BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[llm] .env 로드 실패(무시): {e}")


_load_dotenv()

DASHSCOPE_API_KEY  = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL",
                               "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").rstrip("/")
QWEN_MODEL         = os.getenv("QWEN_MODEL", "qwen3.6-flash").strip()
QWEN_STRONG_MODEL  = os.getenv("QWEN_STRONG_MODEL", "qwen3.7-plus").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

DEFAULT_TIMEOUT = 90
MAX_RETRIES = 3
DEFAULT_MAX_TOKENS = 3000

_TIER_MODEL = {
    "cheap": QWEN_MODEL,
    "strong": QWEN_STRONG_MODEL,
}


def _log_usage(post_id, provider, model, prompt_tokens, completion_tokens, ok, note=""):
    """DB logs 테이블에 사용량 기록 (실패해도 무시)."""
    if post_id is None:
        return
    try:
        from db import get_conn
        msg = (f"[LLM] {provider}/{model} in={prompt_tokens} out={completion_tokens} "
               f"{'OK' if ok else 'FAIL'} {note}").strip()
        conn = get_conn()
        conn.execute(
            "INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'LLM', ?, ?)",
            (post_id, msg, "info" if ok else "warning")
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _call_qwen(prompt, model, max_tokens, temperature, system=None):
    """DashScope OpenAI-호환 엔드포인트를 requests로 직접 호출."""
    import requests
    url = f"{DASHSCOPE_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
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
        raise RuntimeError(f"Qwen HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _call_gemini(prompt, model, max_tokens, temperature, system=None):
    from google import genai
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
        um = getattr(response, "usage_metadata", None)
        if um:
            pt = getattr(um, "prompt_token_count", 0) or 0
            ct = getattr(um, "candidates_token_count", 0) or 0
    except Exception:
        pass
    return text, pt, ct


def _provider_chain(tier):
    qwen_model = _TIER_MODEL.get(tier, QWEN_MODEL)
    chain = []
    if DASHSCOPE_API_KEY:
        chain.append(("QWEN", _call_qwen, qwen_model))
    if GEMINI_API_KEY:
        chain.append(("GEMINI", _call_gemini, GEMINI_MODEL))
    return chain


def generate(prompt, tier="cheap", max_tokens=DEFAULT_MAX_TOKENS,
             temperature=0.8, system=None, post_id=None):
    """
    텍스트를 생성해 반환합니다.
    tier: "cheap"(기본, 대량/가벼운 작업) | "strong"(고품질 윤색)
    모든 공급자가 실패하면 마지막 예외를 raise 합니다.
    """
    chain = _provider_chain(tier)
    if not chain:
        raise RuntimeError("사용 가능한 LLM API 키가 없습니다 (.env의 DASHSCOPE_API_KEY / GEMINI_API_KEY 확인).")

    last_error = None
    for idx, (name, fn, model) in enumerate(chain):
        for attempt in range(MAX_RETRIES):
            try:
                text, pt, ct = fn(prompt, model, max_tokens, temperature, system)
                if text and text.strip():
                    note = "(fallback)" if idx > 0 else ""
                    _log_usage(post_id, name, model, pt, ct, True, note)
                    return text.strip()
                raise RuntimeError("빈 응답")
            except Exception as e:
                last_error = e
                _log_usage(post_id, name, model, 0, 0, False, f"({attempt + 1}/{MAX_RETRIES}) {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5 * (2 ** attempt))
    raise RuntimeError(f"모든 LLM 공급자 호출 실패. 마지막 오류: {last_error}")


def available_providers():
    """현재 키가 설정된 공급자 목록 (디버그/상태 표시용)."""
    out = []
    if DASHSCOPE_API_KEY:
        out.append(f"qwen({QWEN_MODEL})")
    if GEMINI_API_KEY:
        out.append(f"gemini({GEMINI_MODEL})")
    return out


if __name__ == "__main__":
    print("설정된 공급자:", available_providers())
    try:
        ans = generate("한 문장으로 인사말을 작성하세요.", tier="cheap", max_tokens=80)
        print("Qwen 응답:", ans)
    except Exception as e:
        print("Qwen 실패:", e)
