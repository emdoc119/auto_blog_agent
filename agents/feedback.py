import os
import sys
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_STATE_FILE, GEMINI_API_KEY
from db import get_conn

def scrape_blog_stats():
    """블로그 홈에서 텍스트를 긁어와 대략적인 상태나 최신 글을 확인합니다."""
    stats_text = ""
    if not os.path.exists(NAVER_STATE_FILE):
        return "로그인 세션이 없습니다."
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=NAVER_STATE_FILE)
            page = context.new_page()
            page.goto("https://section.blog.naver.com/BlogHome.naver", timeout=30000)
            time.sleep(2)
            
            try:
                page.locator("a:has-text('내 블로그')").first.click(timeout=5000)
                time.sleep(3)
                stats_text = page.locator("body").inner_text()[:2000]
            except:
                stats_text = "내 블로그 버튼을 찾을 수 없거나 이동 실패."
                
            browser.close()
    except Exception as e:
        print("Scraping failed:", e)
        stats_text = f"통계 수집 실패: {e}"
        
    return stats_text

def analyze_and_update_strategy(project_id: int):
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    
    if not project or project["status"] != "active":
        return
        
    print(f"🕵️ [Feedback Agent] 프로젝트 {project_id} 통계 및 반응 분석 시작...")
    stats_text = scrape_blog_stats()
    
    prompt = f"""
당신은 대한민국 상위 1% 조회수를 기록하는 네이버 블로그 전문 마케팅 컨설턴트입니다.
우리는 현재 '{project['title']}' 라는 주제의 블로그 프로젝트를 운영 중입니다.

아래는 방금 블로그 메인 화면에서 긁어온 현황 데이터입니다.
[블로그 현황 데이터]
{stats_text}

위 데이터를 바탕으로, 내일 글을 작성할 AI 작가(Writer)가 글의 퀄리티를 극적으로 끌어올릴 수 있도록 **'글쓰기 전략 수정 지침(Action Plan)'**을 정확히 3줄로 지시해주세요.

🌟 반드시 다음 3가지 핵심 관점을 각각 1줄씩 포함해야 합니다:
1. **어조 및 말투 (Tone & Manner):** 타겟 독자층에 맞춘 친근함, 전문성, 공감성 조절 지시
2. **도입부 후킹 (Hook Strategy):** 체류시간을 늘리기 위한 질문 던지기, 두괄식 결론 제시 등 구체적인 기법 지시
3. **시각 및 구조 (Visuals & Structure):** 이모지 사용, 표/인용구 배치, 줄바꿈 등 가독성 극대화 지시

출력형식 (반드시 3줄 요약만 출력, 각 줄은 '-' 로 시작):
- [어조/말투 지시사항]
- [도입부 후킹 지시사항]
- [시각적 구조 지시사항]
"""
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
        )
        feedback = response.text.strip()
    except Exception as e:
        print("Gemini API Error:", e)
        feedback = "- 최신 트렌드를 반영하여 가독성 높게 작성하세요.\n- 독자와 소통하는 부드러운 말투를 사용하세요.\n- 전문성을 어필하되 쉽게 풀어쓰세요."
        
    conn = get_conn()
    conn.execute("UPDATE projects SET strategy_feedback = ? WHERE id = ?", (feedback, project_id))
    conn.commit()
    conn.close()
    print(f"✅ [Feedback Agent] 전략 업데이트 완료:\n{feedback}")

if __name__ == "__main__":
    # 테스트용
    analyze_and_update_strategy(1)
