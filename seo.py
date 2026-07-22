"""
SEO 모듈
글의 제목/본문/키워드로 네이버 블로그 검색 태그(키워드) 를 생성합니다.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm

NL = chr(10)


def generate_tags(title, content, keywords="", count=8):
    """글에 적합한 SEO 태그 리스트를 반환 (실패 시 [])."""
    prompt = NL.join([
        f"아래 네이버 블로그 글에 적합한 검색 태그(키워드) {count}개를 생성하세요.",
        "각 태그는 2~4어절 명사구로, 실제 사용자가 검색할 만한 자연어 키워드로 만드세요.",
        "반드시 쉼표로 구분해 태그만 출력하세요 (번호·설명·기호 금지).",
        "예시: 오십견 증상, 어깨 통증 스트레칭, 유착성 관절낭염",
        "",
        f"주요 키워드: {keywords}",
        f"제목: {title}",
        f"본문 요약: {content[:1500]}",
    ])
    try:
        text = llm.generate(prompt, tier="cheap", max_tokens=120, temperature=0.4)
        raw = text.replace(NL, ",")
        tags = [t.strip().lstrip("-•·* ").strip() for t in raw.split(",")]
        tags = [t for t in tags if t and 1 < len(t) <= 30]
        seen = set()
        out = []
        for t in tags:
            key = t.lower()
            if key not in seen:
                seen.add(key)
                out.append(t)
        return out[:count]
    except Exception:
        return []


if __name__ == "__main__":
    import sys as _s
    t = _s.argv[1] if len(_s.argv) > 1 else "오십견 증상과 스트레칭 관리법"
    print("tags:", generate_tags(t, "오십견은 유착성 관절낭염으로 어깨 통증과 가동범위 감소가 특징입니다.", "오십견, 어깨통증"))
