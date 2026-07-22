"""
Editor Agent (품질 에디터)

Writer 가 작성한 초안을 품질 루브릭 기준으로 다듬어 글의 완성도를 지속적으로 높입니다.
- 사실 관계와 이미지 마크다운(![...](...)) 은 절대 변경/삭제하지 않습니다.
- 에디팅 결과가 비정상적이면(이미지 누락, 과도한 축소) 원본을 유지하는 안전장치 포함.
- 비용 절약을 위해 기본은 cheap 모델 사용 (EDITOR_TIER 로 조절 가능).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn
import llm
from agents.writer import parse_output

EDITOR_TIER = os.getenv("EDITOR_TIER", "cheap")


def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Editor', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()


EDIT_PROMPT = """당신은 네이버 블로그 글의 품질을 끌어올리는 전문 에디터입니다.
아래 글을 다음 품질 기준에 맞춰 다듬으세요. 원문의 사실 관계와 이미지 마크다운(![...](...)) 은 절대 바꾸거나 지우지 말고 위치도 유지하세요.

[품질 기준]
1. 도입부 훅: 첫 인용구와 도입부가 독자의 시선을 잡고 공감을 이끌어내는지. 약하면 강화하세요.
2. 가독성: 문장은 짧고 명료하게, 불필요한 군더더기와 반복은 제거, 문단 길이는 적절하게.
3. 구조: 소제목(##), 인용구(> ), 리스트, 구분선(---) 이 일관되고 깔끔한지 정비.
4. 어조: 전문적이면서도 따뜻한 말투. 광고성·과장 표현은 제거.
5. 마무리: '오늘의 3줄 요약'과 부드러운 행동 유도(CTA) 가 있는지 확인·보완.

[출력 형식] (반드시 이 형식만 출력)
TITLE: [다듬은 제목]
---
[다듬은 본문. 이미지 마크다운은 원문 그대로 유지]

제목: {title}

본문:
{content}
"""


def edit(post_id: int, title: str, content: str) -> tuple:
    """초안을 품질 루브릭으로 다듬어 (title, content) 를 반환. 실패 시 원본 반환."""
    if not content:
        return title, content
    add_log(post_id, "품질 에디팅 시작")
    try:
        prompt = EDIT_PROMPT.format(title=title, content=content[:6000])
        text = llm.generate(prompt, tier=EDITOR_TIER, max_tokens=3500, temperature=0.6, post_id=post_id)
        new_title, new_content = parse_output(text)

        # 안전장치 1: 이미지가 사라졌으면 원본 유지
        if content.count("![") > 0 and new_content.count("![") == 0:
            add_log(post_id, "에디팅 후 이미지 누락 -> 원본 유지", "warning")
            return title, content
        # 안전장치 2: 결과가 과도하게 짧아졌으면 원본 유지
        if len(new_content) < len(content) * 0.5:
            add_log(post_id, "에디팅 결과가 과도하게 짧음 -> 원본 유지", "warning")
            return title, content

        add_log(post_id, f"품질 에디팅 완료 ({len(content)}자 -> {len(new_content)}자)")
        return (new_title or title), new_content
    except Exception as e:
        add_log(post_id, f"에디팅 실패(원본 유지): {e}", "warning")
        return title, content
