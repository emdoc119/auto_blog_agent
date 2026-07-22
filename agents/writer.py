"""
Writer Agent
수집된 자료를 바탕으로 Claude 또는 OpenAI API를 사용해 블로그 글을 생성합니다.
API 키가 없는 경우 템플릿 기반으로 초안을 생성합니다.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn
from config import REQUIRE_CEO_APPROVAL, AUTO_PUBLISH
import llm

def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Writer', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()

BLOG_PROMPT = """당신은 상위 1% 조회수를 기록하는 최고 수준의 건강/전문 정보 네이버 블로그 마케팅 전문가이자 작가입니다.
주어진 키워드와 자료를 바탕으로, 독자를 완벽하게 사로잡는 고품질 네이버 블로그 글을 작성해 주세요.

주제 키워드: {keywords}
참고 자료:
{research_data}

[프로젝트 기본 전략 지침]
{strategy_feedback}

[경쟁사 트렌드 전략 지침] (상위 노출 블로그 분석 결과)
{trend_strategy}

🌟 고품질 글쓰기 핵심 구조 및 프리미엄 포맷팅 가이드 (반드시 준수!):

1. **도입부 (Hook & Empathy)**:
   - 글의 시작은 무조건 인용구(`> `)를 사용하여 독자의 가장 큰 고민이나 질문을 콕 짚어냅니다.
   - 예시: `> "밤마다 쑤시는 어깨 통증, 혹시 나도 오십견일까 고민하셨나요?"`
   - 이후 따뜻하고 공감가는 문체로 도입부를 풀어갑니다.

2. **본론 (Data & Education)**:
   - 본론은 반드시 2~3개의 명확한 소제목(`## 📌 [소제목]`)으로 나눕니다.
   - 각 소제목과 소제목 사이에는 반드시 마크다운 구분선(`---`)을 넣어 시각적 피로도를 줄이세요.
   - 텍스트가 뭉쳐있지 않도록 불릿포인트(`- `)나 숫자(`1. `) 리스트를 적극 활용하여 가독성을 높입니다.
   - 전문가적 견해나 의학적 조언을 적을 때는 핵심 박스(인용구 `> 💡 전문의의 조언: ...`)를 활용하여 강조하세요.

3. **결론부 (Actionable Takeaway & CTA)**:
   - 본문의 내용이 끝난 후 구분선(`---`)을 넣고, `## ✅ 오늘의 3줄 요약`을 작성하세요.
   - 결론 박스(`> 1. ... \n> 2. ... \n> 3. ...`) 형태로 3가지를 정리해 줍니다.
   - 마지막에는 독자가 취해야 할 행동(진료 권유, 이웃 추가, 꾸준한 건강 관리 등)을 부드럽게 유도하며 마무리합니다.

🎨 시각적 요소(Visuals) 필수 가이드:
- **마크다운 표(Table):** 정보를 비교할 때 표를 사용하세요. 표 전후로는 반드시 빈 줄(Enter)을 넣어야 표가 깨지지 않습니다.
- **문맥 맞춤형 AI 이미지 적극 삽입 (3~4개 필수):** 타겟 독자의 이해를 돕기 위해 구간마다 이미지를 삽입하세요.
  - 질병/해부학 설명 시: `clear_medical_illustration_of_shoulder_joint_pain_white_background`
  - 논문/AI/약물 설명 시: `clean_flat_design_concept_art_showing_AI_data_analysis_workflow`
  - 형식: `![이미지 설명](https://image.pollinations.ai/prompt/{{영어로_번역된_매우_구체적이고_긴_프롬프트}}?width=800&height=600&nologo=true)`

작성 규칙:
1. **경쟁 블로그 압도:** 참고 자료(상위 노출 블로그)의 제목과 구조를 뛰어넘는 훨씬 매력적이고 세련된 제목(30자 내외)과 풍성한 내용을 작성하세요.
2. 본문 분량은 1500~2000자 분량으로 작성.
3. 광고성 문구 금지, 순수 정보성/전문성을 어필하되 친절한 말투 사용.
4. [중요] 주어진 참고 자료를 절대 그대로 짜깁기하지 말고, 100% 본인만의 새로운 문장으로 재창작.
5. [중요] 블로그 이름을 언급할 때는 반드시 "응급의학과 의사와 함께 건강하게 100세 까지" 라고 하세요.

출력 형식:
TITLE: [매력적인 제목]
---
[프리미엄 포맷팅이 적용된 본문 내용]
"""


def write_template(keywords: str, research_data: str) -> tuple[str, str]:
    """API 키 없을 때 사용하는 기본 템플릿"""
    kw_list = [k.strip() for k in keywords.split(",")]
    main_kw = kw_list[0] if kw_list else "건강"
    
    title = f"{main_kw}에 대해 꼭 알아야 할 핵심 정보"
    content = f"""안녕하세요! 오늘은 {main_kw}에 대해 알아보겠습니다.

## {main_kw}란 무엇인가요?

{main_kw}은 현대인들에게 매우 중요한 건강 주제 중 하나입니다.
올바른 정보를 통해 건강한 생활을 유지하는 것이 중요합니다.

## 핵심 정보 요약

아래는 수집된 자료를 바탕으로 한 핵심 정보입니다:

{research_data[:500] if research_data and research_data != '수집된 자료 없음' else '관련 정보를 준비 중입니다.'}

## 생활 속 실천 방법

1. 규칙적인 생활 습관 유지
2. 균형 잡힌 식단 섭취
3. 적절한 운동과 충분한 수면

## 마무리

⭐ 핵심 요약:
- {main_kw}은 건강한 생활의 중요한 요소입니다
- 꾸준한 관리와 올바른 정보가 필요합니다
- 전문가와 상담을 통해 개인에게 맞는 방법을 찾아보세요

※ 이 글은 정보 제공 목적으로 작성되었으며, 의학적 진단이나 처방을 대체하지 않습니다.
"""
    return title, content

def parse_output(text: str) -> tuple[str, str]:
    """AI 출력에서 제목과 본문 분리"""
    if "TITLE:" in text and "---" in text:
        parts = text.split("---", 1)
        title = parts[0].replace("TITLE:", "").strip()
        content = parts[1].strip() if len(parts) > 1 else text
    else:
        lines = text.strip().split("\n")
        title = lines[0].lstrip("#").strip()
        content = "\n".join(lines[1:]).strip()
    return title, content

def write(post_id: int, keywords: str, research_data: str, trend_strategy: str = ""):
    """메인 글쓰기 함수. llm.generate() 사용 (1순위 Qwen, 폴백 Gemini)."""
    add_log(post_id, f"글쓰기 시작: {keywords}")

    conn = get_conn()
    post = conn.execute("SELECT project_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    project = conn.execute("SELECT strategy_feedback FROM projects WHERE id = ?", (post["project_id"],)).fetchone() if post else None
    conn.close()

    strategy = project["strategy_feedback"] if project and project["strategy_feedback"] else "자유롭게 고품질의 글을 작성하세요."

    try:
        prompt = BLOG_PROMPT.format(
            keywords=keywords,
            research_data=(research_data or "")[:6000],
            strategy_feedback=strategy,
            trend_strategy=trend_strategy or "",
        )
        # 1차 초안: 저렴한 모델로 대량 생성
        text = llm.generate(prompt, tier="cheap", max_tokens=3000, temperature=0.85, post_id=post_id)
        title, content = parse_output(text)

        # 분량이 너무 짧을 때만 강한 모델로 1회 보강 (토큰 절약)
        if len(content) < 600:
            add_log(post_id, "초안 분량 부족 -> 강한 모델로 보강 시도", "warning")
            polish_prompt = f"""아래 블로그 글을 1500~2000자 분량으로 더 풍부하고 가독성 좋게 보완하세요.
마크다운 소제목, 인용구, 리스트, 3줄 요약 구조를 유지하세요.

제목: {title}

본문:
{content[:4000]}"""
            try:
                text2 = llm.generate(polish_prompt, tier="strong", max_tokens=3000, temperature=0.8, post_id=post_id)
                t2, c2 = parse_output(text2)
                if len(c2) > len(content):
                    title, content = (t2 or title), c2
            except Exception as pe:
                add_log(post_id, f"보강 실패(초안 유지): {pe}", "warning")

    except Exception as e:
        add_log(post_id, f"글쓰기 최종 실패: {e}", "error")
        conn = get_conn()
        conn.execute("UPDATE posts SET status = 'error' WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
        return "", ""

    if AUTO_PUBLISH:
        next_status = "scheduled"
    elif REQUIRE_CEO_APPROVAL:
        next_status = "pending_approval"
    else:
        next_status = "approved"

    conn = get_conn()
    conn.execute(
        "UPDATE posts SET title = ?, content = ?, status = ? WHERE id = ?",
        (title, content, next_status, post_id)
    )
    conn.commit()
    conn.close()

    add_log(post_id, f"글쓰기 완료. 상태: {next_status}")
    return title, content
