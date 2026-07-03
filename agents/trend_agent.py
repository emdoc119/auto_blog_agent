import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY
from db import get_conn

def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'TrendAgent', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()

def search_competitors(keyword: str) -> str:
    from playwright.sync_api import sync_playwright
    result_text = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://search.naver.com/search.naver?where=blog&query={keyword}", timeout=15000)
            time.sleep(2)
            
            # 상위 블로그 텍스트 추출 (제목, 요약 등)
            snippets = page.locator(".total_tit, .api_txt_lines").all_inner_texts()
            if snippets:
                result_text = "\n\n".join(snippets[:10])
            else:
                result_text = page.locator("body").inner_text()[:3000]
            browser.close()
    except Exception as e:
        print(f"경쟁사 검색 실패: {e}")
        return "경쟁사 데이터를 수집하지 못했습니다."
    
    return result_text

def analyze_trends(post_id: int, keywords: list[str]) -> str:
    """
    경쟁사 분석을 통해 글쓰기 트렌드 전략을 도출합니다.
    """
    if not keywords:
        return "자유롭게 고품질의 글을 작성하세요."
        
    main_kw = keywords[0]
    add_log(post_id, f"'{main_kw}' 키워드로 상위 노출 경쟁사 분석 시작...")
    
    competitor_data = search_competitors(main_kw)
    
    if "수집하지 못했습니다" in competitor_data or not competitor_data.strip():
        add_log(post_id, "경쟁사 데이터 부족, 기본 전략 사용", "warning")
        return "상위 노출 블로그 분석 실패. 독자 친화적인 고품질 글로 승부하세요."
        
    prompt = f"""
당신은 블로그 트렌드 분석가입니다.
우리가 작성할 메인 키워드는 '{main_kw}' 입니다.

아래는 현재 네이버 검색 상위에 노출된 경쟁 블로그들의 제목과 요약 내용입니다:
[경쟁사 데이터]
{competitor_data[:2000]}

이 내용을 분석해서, 내일(또는 오늘) 우리가 쓸 블로그 글이 저 경쟁사들을 압도하고 독자의 클릭과 체류시간을 늘릴 수 있는 **'작성 전략 가이드(3~4줄)'**를 제시해 주세요.
예: "경쟁사들은 A를 강조하니 우리는 B의 관점을 추가하여 차별화하세요." 등.
부가설명 없이 지침만 나열하세요.
"""
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
        )
        feedback = response.text.strip()
        add_log(post_id, "경쟁사 분석 완료 및 트렌드 전략 도출")
        return feedback
    except Exception as e:
        add_log(post_id, f"트렌드 분석 실패: {e}", "warning")
        return "독자에게 도움이 되는 실용적인 정보를 최우선으로 작성하세요."

if __name__ == "__main__":
    # 테스트
    print(search_competitors("응급실 웰니스"))
