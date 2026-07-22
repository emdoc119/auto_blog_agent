"""
저작권 프리 이미지 소스 (Pexels)

글의 키워드/주제로 Pexels 에서 저작권 프리 실사 사진을 검색해 반환합니다.
Pexels 라이선스: 출처 표기 없이 상업적 사용 가능.
API 키는 .env 의 PEXELS_API_KEY (gitignore 대상).
"""
import os
import requests

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_key():
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(_BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return ""
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("PEXELS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


PEXELS_API_KEY = _load_key()
SEARCH_URL = "https://api.pexels.com/v1/search"


def fetch_photos(query, count=3, orientation="landscape"):
    """
    Pexels 에서 키워드로 저작권 프리 사진을 검색합니다.
    반환: [{"url", "alt", "photographer"}, ...] (실패/키 없으면 [])
    """
    if not PEXELS_API_KEY or not query:
        return []
    try:
        r = requests.get(
            SEARCH_URL,
            params={"query": query, "per_page": max(count + 2, 5), "orientation": orientation},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        photos = r.json().get("photos", [])
        result = []
        for p in photos:
            src = p.get("src", {})
            url = src.get("large2x") or src.get("large") or src.get("original")
            if not url:
                continue
            alt = (p.get("alt") or query).strip()
            if len(alt) > 80:
                alt = alt[:80]
            result.append({"url": url, "alt": alt, "photographer": p.get("photographer", "")})
            if len(result) >= count:
                break
        return result
    except Exception:
        return []


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "healthy lifestyle"
    print("key loaded:", bool(PEXELS_API_KEY))
    for ph in fetch_photos(q, count=3):
        print(" -", ph["alt"][:50], "|", ph["url"][:80])
