import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================
# ✏️  여기에 설정을 입력하세요
# =====================================================

# 에이전트 설정
# 아래에 발급받은 API 키를 입력하세요 (claude, openai, gemini 중 하나 이상)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCipk3wDtTNp74uKaFRgaoracSoQd2Q_c8")

# 사용할 AI 공급자 (gemini, anthropic, openai)
AI_PROVIDER = "gemini" 

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
