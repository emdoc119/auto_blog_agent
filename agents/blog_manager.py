import sys
import os
import json
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import llm
from db import get_conn

def generate_blog_proposal(account_id: int):
    """AI를 통해 블로그 카테고리, 프로필, 배경 이미지 프롬프트를 기획하고 DB에 저장"""
    prompt = """
당신은 대한민국 상위 1% 네이버 블로그 관리 및 브랜딩 전문가입니다.
현재 관리할 블로그는 '응급의학과 전문의가 알려주는 건강, 논문 작성 꿀팁 및 의학 정보'를 주제로 합니다.

다음 3가지를 완벽하게 기획하여 JSON 형식으로만 응답해주세요. (다른 설명은 절대 금지)
1. "profile_bio": 블로그 프로필(소개글) 문구. (신뢰감을 주면서도 친근한 말투, 50자 이내)
2. "categories": 이 블로그에 꼭 필요한 게시판(카테고리) 이름 리스트. (배열 형태, 총 5~6개. 예: "응급실 이야기", "의학 논문 리뷰", "알기 쉬운 건강 상식" 등)
3. "image_prompt": 이 블로그의 프로필 사진으로 쓰일 고품질 일러스트레이션을 생성하기 위한 영문 프롬프트. (예: "A professional and friendly Korean emergency doctor with a stethoscope, flat illustration style, clean white background, vibrant colors")

반드시 JSON 형식으로만 반환하세요.
{
  "profile_bio": "...",
  "categories": ["...", "..."],
  "image_prompt": "..."
}
"""
    try:
        # JSON 파싱 (코드 블록 제거)
        result_text = llm.generate(prompt, tier="cheap", max_tokens=800, temperature=0.7)
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        proposal = json.loads(result_text.strip())
        
        # 이미지 생성 (Pollinations)
        image_prompt_encoded = urllib.parse.quote(proposal["image_prompt"])
        image_url = f"https://image.pollinations.ai/prompt/{image_prompt_encoded}?width=500&height=500&nologo=true"
        
        # DB 저장
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO blog_proposals (account_id, categories_json, profile_bio, profile_img_url, status) VALUES (?, ?, ?, ?, 'pending_approval')",
            (account_id, json.dumps(proposal["categories"], ensure_ascii=False), proposal["profile_bio"], image_url)
        )
        conn.commit()
        proposal_id = cur.lastrowid
        conn.close()
        
        return proposal_id
        
    except Exception as e:
        print(f"기획 실패: {e}")
        return None

if __name__ == "__main__":
    pid = generate_blog_proposal(1)
    print(f"생성된 제안서 ID: {pid}")
