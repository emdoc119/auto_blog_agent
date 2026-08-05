import sys
import os
import time
from datetime import datetime
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn

def run_stats_scraper():
    """
    모든 활성 계정의 오늘 방문자 수를 수집하여 daily_stats에 저장합니다.
    """
    print("📊 [Stats Scraper] 플랫폼별 방문자 통계 수집 시작...")
    conn = get_conn()
    accounts = conn.execute("SELECT * FROM accounts WHERE status = 'active'").fetchall()
    
    today_str = datetime.now().date().isoformat()
    
    for acc in accounts:
        platform = acc["platform"]
        blog_url = acc["blog_url"]
        account_id = acc["id"]
        
        visitors = None

        if platform == "naver":
            target_url = blog_url if (blog_url and "naver.com" in blog_url) else "https://blog.naver.com/emdoc119"
            visitors = scrape_naver_visitors(target_url)
        else:
            print(f"  -> 계정 {account_id} ({platform}): 지원하지 않는 통계 소스, 건너뜀")

        if visitors is None:
            print(f"  -> 계정 {account_id} ({platform}): 방문자 수 확인 실패, 기존 값 유지")
            continue
            
        # DB에 저장 (UNIQUE 제약조건으로 인해 오늘 날짜 데이터가 있으면 무시되거나 업데이트 해야 함)
        # SQLite UPSERT 구문 사용 (INSERT ON CONFLICT)
        try:
            conn.execute("""
                INSERT INTO daily_stats (account_id, stat_date, visitors)
                VALUES (?, ?, ?)
                ON CONFLICT(account_id, stat_date) DO UPDATE SET
                visitors = excluded.visitors
            """, (account_id, today_str, visitors))
            conn.commit()
            print(f"  -> 계정 {account_id} ({platform}): 오늘 방문자 {visitors}명 수집 완료")
        except Exception as e:
            print(f"  -> 계정 {account_id} DB 저장 실패: {e}")
            
    conn.close()

    # 발행된 글의 조회수 수집 (best-effort, 실패해도 무시)
    try:
        collect_post_views()
    except Exception as e:
        print(f"  [Views] 오류: {e}")

    print("📊 [Stats Scraper] 통계 수집 완료.")

def scrape_naver_visitors(url: str):
    from playwright.sync_api import sync_playwright
    visitors = None
    # 모바일 URL이 방문자 수(오늘 NN)를 가장 명확하게 제공함
    blog_id_match = re.search(r"blog\.naver\.com/([^/?#]+)", url)
    blog_id = blog_id_match.group(1) if blog_id_match else "emdoc119"
    mobile_url = f"https://m.blog.naver.com/{blog_id}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(mobile_url, timeout=20000)
            time.sleep(2)
            
            text = page.locator("body").inner_text()
            
            match = re.search(r'(오늘|Today)\s*([0-9,]+)', text, re.IGNORECASE)
            if match:
                num_str = match.group(2).replace(',', '')
                visitors = int(num_str)
            browser.close()
    except Exception as e:
        print(f"Naver 스크래핑 오류 ({mobile_url}): {e}")

    return visitors

def _fetch_post_views(page, pid):
    """네이버 글 페이지에서 조회수를 읽어 반환 (못 찾으면 None)."""
    url = f"https://blog.naver.com/emdoc119/{pid}"
    try:
        page.goto(url, timeout=30000)
        time.sleep(2)
        for fr in page.frames:
            try:
                txt = fr.locator("body").inner_text(timeout=3000)
                m = re.search(r"조회\s*([0-9,]+)", txt)
                if m:
                    return int(m.group(1).replace(",", ""))
            except Exception:
                continue
    except Exception:
        pass
    return None


def collect_post_views():
    """발행된 글의 조회수를 블로그에서 수집해 posts.views 에 저장 (best-effort)."""
    from playwright.sync_api import sync_playwright
    import requests
    import xml.etree.ElementTree as ET
    state = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "naver_state.json")
    if not os.path.exists(state):
        print("  [Views] 로그인 세션 없음, 건너뜀")
        return
    try:
        r = requests.get("https://rss.blog.naver.com/emdoc119.xml",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  [Views] RSS 조회 실패: {e}")
        return
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        m = re.search(r"emdoc119/(\d+)", link)
        if title and m:
            items.append((m.group(1), title))
    items = items[:10]
    if not items:
        return
    updated = 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=state)
            page = ctx.new_page()
            conn = get_conn()
            for pid, title in items:
                views = _fetch_post_views(page, pid)
                if views is None:
                    continue
                row = conn.execute(
                    "SELECT id FROM posts WHERE status='published' AND title=? ORDER BY id DESC LIMIT 1",
                    (title,)).fetchone()
                if row:
                    conn.execute("UPDATE posts SET views=? WHERE id=?", (views, row["id"]))
                    updated += 1
            conn.commit()
            conn.close()
            browser.close()
        print(f"  [Views] {updated}개 글 조회수 갱신")
    except Exception as e:
        print(f"  [Views] 수집 실패: {e}")

if __name__ == "__main__":
    run_stats_scraper()
