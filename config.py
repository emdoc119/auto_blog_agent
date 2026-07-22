import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """.env 파일을 os.environ에 로드 (이미 있으면 덮어쓰지 않음)."""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[config] .env 로드 실패(무시): {e}")


_load_dotenv()

# =====================================================
# ✏️  여기에 설정을 입력하세요
# =====================================================

# 에이전트 설정
# API 키는 .env 파일 또는 환경변수로 관리합니다 (코드에 직접 입력하지 마세요).
# .env 예시: DASHSCOPE_API_KEY=sk-...  /  GEMINI_API_KEY=...
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# LLM 라우팅은 llm.py가 담당합니다 (1순위 Qwen, 폴백 Gemini).
# 아래 값은 하위 호환용으로만 유지됩니다.
AI_PROVIDER = "qwen"

# 자동화 딜레이 (초)
AGENT_DELAY = 5

# 네이버 블로그 자동 발행 스크립트 경로 (blog_agent 내부)
PUBLISHER_SCRIPT  = os.path.join(BASE_DIR, "auto_post.py")
PUBLISHER_VENV    = os.path.abspath(os.path.join(BASE_DIR, "..", "venv", "bin", "python"))

# 로그인 쿠키 파일 경로 (blog_agent 내부)
NAVER_STATE_FILE  = os.path.join(BASE_DIR, "naver_state.json")

# 데이터베이스
DB_PATH = os.path.join(BASE_DIR, "blog_agent_v2.db")

# 발행 기본 설정
DEFAULT_BLOG_CATEGORY = "건강"   # 네이버 블로그 카테고리

# CEO 승인 방식: True = 초안 확인 후 수동 승인 / False = 완전 자동 발행
REQUIRE_CEO_APPROVAL = False

# 완전 자동 스케줄 발행 여부 (True 시 승인 대기 없이 바로 스케줄 예약됨)
AUTO_PUBLISH = True

# Flask 설정
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001
FLASK_SECRET_KEY = "blog-agent-secret-2026"
