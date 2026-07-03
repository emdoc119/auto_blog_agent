"""
Researcher Agent
네이버 검색을 통해 키워드 관련 자료를 수집합니다.
"""
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn

def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Researcher', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()

def research(post_id: int, keywords: list[str]) -> str:
    """
    키워드 리스트를 받아 네이버에서 자료를 수집하고 요약 텍스트를 반환합니다.
    """
    from playwright.sync_api import sync_playwright
    
    add_log(post_id, f"자료 수집 시작: {keywords}")
    
    collected = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        for keyword in keywords[:3]:  # 최대 3개 키워드
            try:
                add_log(post_id, f"키워드 검색 중: {keyword}")
                
                # 네이버 블로그 검색
                search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
                page.goto(search_url, timeout=30000)
                time.sleep(2)
                
                # 검색 결과 제목과 요약문 수집
                items = page.locator("ul.lst_view li.bx, .lst_total .bx").all()
                
                for item in items[:5]:  # 상위 5개
                    try:
                        title_el = item.locator(".title_link, .api_txt_lines.total_tit").first
                        desc_el  = item.locator(".dsc_link, .api_txt_lines.dsc_txt").first
                        
                        title = title_el.inner_text(timeout=2000) if title_el.count() > 0 else ""
                        desc  = desc_el.inner_text(timeout=2000)  if desc_el.count() > 0 else ""
                        
                        if title and len(title) > 3:
                            collected.append(f"[{keyword}] {title}\n{desc}")
                    except:
                        continue
                        
            except Exception as e:
                add_log(post_id, f"키워드 '{keyword}' 수집 실패: {e}", "warning")
                continue
        
        browser.close()
    
    research_text = "\n\n---\n\n".join(collected) if collected else "수집된 자료 없음"
    
    # DB에 저장
    conn = get_conn()
    conn.execute("UPDATE posts SET research_data = ?, status = 'writing' WHERE id = ?",
                 (research_text, post_id))
    conn.commit()
    conn.close()
    
    add_log(post_id, f"자료 수집 완료: {len(collected)}건")
    return research_text
