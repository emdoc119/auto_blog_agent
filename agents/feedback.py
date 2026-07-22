import os
import sys
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_STATE_FILE
import llm
from db import get_conn

NL = chr(10)


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
            except Exception:
                stats_text = "내 블로그 버튼을 찾을 수 없거나 이동 실패."
            browser.close()
    except Exception as e:
        print("Scraping failed:", e)
        stats_text = f"통계 수집 실패: {e}"
    return stats_text


def _performance_summary(project_id):
    """프로젝트의 발행된 글 성과(조회수+품질점수) 요약 문자열과 상위 글 제목 목록 반환."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT title, views, quality_score FROM posts "
        "WHERE project_id=? AND status='published' "
        "ORDER BY COALESCE(views,0) DESC, COALESCE(quality_score,0) DESC LIMIT 15",
        (project_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return "아직 발행된 글의 성과 데이터가 없습니다.", []
    lines = []
    for r in rows:
        v = r["views"] if r["views"] is not None else "-"
        q = r["quality_score"] if r["quality_score"] is not None else "-"
        lines.append(f"- {r['title']} (조회수 {v} / 품질점수 {q})")
    top = [r["title"] for r in rows[:3]]
    return NL.join(lines), top


def analyze_and_update_strategy(project_id: int):
    """블로그 현황 + 글별 성과(조회수/품질점수) 를 분석해 글쓰기 전략을 갱신합니다."""
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()

    if not project or project["status"] != "active":
        return

    print(f"🕵️ [Feedback Agent] 프로젝트 {project_id} 성과 기반 전략 분석 시작...")
    stats_text = scrape_blog_stats()
    perf_text, top_titles = _performance_summary(project_id)

    prompt = f"""당신은 대한민국 상위 1% 조회수를 기록하는 네이버 블로그 전문 마케팅 컨설턴트입니다.
프로젝트: '{project['title']}'

[블로그 현황 데이터]
{stats_text}

[최근 발행 글의 성과 (조회수 / 품질점수)]
{perf_text}

위 성과 데이터를 분석해, 다음 글을 쓸 AI 작가가 글의 퀄리티와 조회수를 함께 끌어올리도록 '글쓰기 전략 지침'을 정확히 3줄로 지시하세요.
잘 되는 글(상위 항목)의 공통점은 살리고, 품질점수가 낮은 글의 약점은 보완하는 데이터 기반 방향이어야 합니다.

반드시 다음 3가지 관점을 각각 1줄씩:
1. 어조/말투: 타겟 독자에 맞는 친근함·전문성·공감성 조절
2. 도입부 후킹: 체류시간을 늘리는 질문·두괄식 결론 등 구체 기법
3. 구조/시각: 소제목·인용구·표·리스트·실사 사진 배치 등 가독성

출력형식 (3줄만, 각 줄 '-' 시작):
- [어조/말투]
- [도입부 후킹]
- [구조/시각]
"""
    try:
        feedback = llm.generate(prompt, tier="cheap", max_tokens=600)
    except Exception as e:
        print("Feedback LLM Error:", e)
        feedback = NL.join([
            "- 최신 트렌드를 반영해 가독성 높게 작성하세요.",
            "- 독자와 소통하는 부드러운 말투를 사용하세요.",
            "- 전문성을 어필하되 쉽게 풀어쓰세요.",
        ])

    conn = get_conn()
    conn.execute("UPDATE projects SET strategy_feedback = ? WHERE id = ?", (feedback, project_id))
    conn.commit()
    conn.close()
    print(f"✅ [Feedback Agent] 전략 업데이트 완료:{NL}{feedback}")


if __name__ == "__main__":
    analyze_and_update_strategy(1)
