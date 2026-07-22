"""
Researcher Agent
키워드 관련 자료를 수집합니다: 신뢰 출처(PubMed/arXiv/Semantic Scholar) + 네이버 블로그 트렌드.
"""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn

NL = chr(10)


def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Researcher', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()


def _infer_topic(project):
    """프로젝트 정보로 주제 유형 추론 (medical / academic / auto)."""
    if not project:
        return "auto"
    text = f"{project['title']} {project['category_name'] or ''} {project['keywords'] or ''}".lower()
    medical = ["건강", "의학", "응급", "질환", "치료", "약", "위고비", "마운자로", "다이어트",
               "통증", "병원", "증상", "100세", "불면", "불안", "고혈압", "피부", "관절", "운동"]
    academic = ["논문", "연구", "학술", "sci", "대학원", "pubmed", "레퍼런스", "영작", "교정", "참고문헌", "연구생산성"]
    is_med = any(k in text for k in medical)
    is_acad = any(k in text for k in academic)
    if is_med and not is_acad:
        return "medical"
    if is_acad and not is_med:
        return "academic"
    return "auto"


def research(post_id: int, keywords: list) -> str:
    from playwright.sync_api import sync_playwright
    add_log(post_id, f"자료 수집 시작: {keywords}")

    # 프로젝트 정보로 주제 유형 추론
    conn = get_conn()
    post = conn.execute("SELECT project_id FROM posts WHERE id=?", (post_id,)).fetchone()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (post["project_id"],)).fetchone() if post else None
    conn.close()
    topic = _infer_topic(project)

    sections = []

    # 1) 신뢰 출처 (PubMed / arXiv / Semantic Scholar)
    try:
        import sources
        kw_str = ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
        auth = sources.search_authoritative(kw_str, topic=topic, count=3)
        if auth:
            lines = ["[권위 있는 학술/의학 출처]"]
            for r in auth:
                lines.append(f"- [{r['source']}] {r['title']}")
                if r.get("snippet"):
                    lines.append(f"  {r['snippet']}")
                if r.get("url"):
                    lines.append(f"  출처: {r['url']}")
            sections.append(NL.join(lines))
            add_log(post_id, f"신뢰 출처 {len(auth)}건 수집 (topic={topic})")
    except Exception as e:
        add_log(post_id, f"신뢰 출처 수집 실패: {e}", "warning")

    # 2) 네이버 블로그 검색 (국내 트렌드/맥락)
    collected = []
    for attempt in range(3):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                page = context.new_page()
                for keyword in keywords[:3]:
                    try:
                        add_log(post_id, f"키워드 검색 중: {keyword}")
                        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
                        page.goto(search_url, timeout=30000)
                        time.sleep(2)
                        items = page.locator("ul.lst_view li.bx, .lst_total .bx").all()
                        for item in items[:5]:
                            try:
                                title_el = item.locator(".title_link, .api_txt_lines.total_tit").first
                                desc_el = item.locator(".dsc_link, .api_txt_lines.dsc_txt").first
                                title = title_el.inner_text(timeout=2000) if title_el.count() > 0 else ""
                                desc = desc_el.inner_text(timeout=2000) if desc_el.count() > 0 else ""
                                if title and len(title) > 3:
                                    collected.append(f"[{keyword}] {title}" + NL + desc)
                            except Exception:
                                continue
                    except Exception as e:
                        add_log(post_id, f"키워드 '{keyword}' 수집 실패: {e}", "warning")
                        continue
                browser.close()
            break
        except Exception as e:
            add_log(post_id, f"Playwright 오류 ({attempt+1}/3) 재시도: {e}", "warning")
            time.sleep(10)
            if attempt == 2:
                add_log(post_id, "Playwright 최종 실패", "error")

    if collected:
        sections.append("[네이버 블로그 트렌드 자료]" + NL + NL.join(collected))

    sep = NL + NL + "---" + NL + NL
    research_text = sep.join(sections) if sections else "수집된 자료 없음"

    conn = get_conn()
    conn.execute("UPDATE posts SET research_data=?, status='writing' WHERE id=?", (research_text, post_id))
    conn.commit()
    conn.close()
    add_log(post_id, f"자료 수집 완료: {len(sections)}섹션 (topic={topic})")
    return research_text
