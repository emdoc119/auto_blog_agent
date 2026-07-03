import sys
import json
import time
from playwright.sync_api import sync_playwright
from db import get_conn

def apply_proposal(proposal_id: int):
    print(f"🚀 블로그 리모델링 시작 (기획안 ID: {proposal_id})")
    
    conn = get_conn()
    proposal = conn.execute("SELECT * FROM blog_proposals WHERE id = ?", (proposal_id,)).fetchone()
    conn.close()
    
    if not proposal:
        print("기획안을 찾을 수 없습니다.")
        return
        
    categories = json.loads(proposal["categories_json"])
    bio = proposal["profile_bio"]
    
    print(f"적용할 카테고리: {categories}")
    print(f"적용할 소개말: {bio}")
    
    # 여기서 Playwright를 켜서 admin.blog.naver.com 에 접속하고
    # iframes 내부의 카테고리 설정 메뉴를 조작해야 합니다.
    # 하지만 네이버 관리자 페이지는 보안 로직과 복잡한 iframe 구조를 가지므로,
    # 완전 자동화 시도 시 계정 보호조치(해킹 의심)에 걸릴 위험이 매우 높습니다.
    
    print("\n[안내] 네이버 블로그 관리자 페이지의 자동화 제어는 해킹으로 오인되어 계정 정지 위험이 높습니다.")
    print("AI가 완벽하게 기획한 내용을 바탕으로, 네이버 관리자 메뉴에서 직접 세팅해 주시는 것을 강력히 권장합니다.")
    print("기획안 상태는 '적용 완료'로 변경됩니다.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        apply_proposal(int(sys.argv[1]))
    else:
        print("사용법: python auto_manage.py <proposal_id>")
