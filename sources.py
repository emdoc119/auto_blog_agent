"""
신뢰 출처 검색 모듈 (Research Sources)

주제별로 권위 있는 출처에서 자료를 검색합니다. 모두 API 키 없이 무료 사용 가능.
- PubMed (의학/건강) : NCBI E-utilities
- arXiv (학술/CS)    : arXiv API
- Semantic Scholar (광범위 학술) : Graph API
한국어 키워드는 LLM(cheap) 으로 영문 검색어로 변환해 검색 품질을 높입니다.
"""
import requests
import xml.etree.ElementTree as ET

TIMEOUT = 25
UA = {"User-Agent": "blog-agent-research/1.0"}
NL = chr(10)


def _translate_keywords(keywords):
    """한국어 키워드(들)를 간결한 영문 검색어 리스트로 변환."""
    try:
        import llm
        q = llm.generate(
            "다음 한국어 키워드들을 각각 간결한 영문 검색어(1~3단어)로 변환하세요. "
            "쉼표로 구분해 영문만 출력하세요 (설명·번호 금지). "
            f"키워드: {keywords}",
            tier="cheap", max_tokens=60, temperature=0.2,
        )
        terms = [t.strip() for t in q.split(",") if t.strip()]
        return terms or [keywords]
    except Exception:
        return [keywords]


def search_pubmed(query, count=3):
    """PubMed 에서 관련 논문(제목+초록) 검색."""
    results = []
    try:
        es = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": count, "retmode": "json", "sort": "relevance"},
            headers=UA, timeout=TIMEOUT,
        )
        if es.status_code != 200:
            return []
        ids = es.json().get("esearchresult", {}).get("idlist", [])[:count]
        if not ids:
            return []
        ef = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            headers=UA, timeout=TIMEOUT,
        )
        if ef.status_code != 200:
            return []
        root = ET.fromstring(ef.content)
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID", "")
            title = (art.findtext(".//ArticleTitle", "") or "").strip()
            journal = (art.findtext(".//Journal/Title", "") or "").strip()
            abstract = " ".join((t.text or "") for t in art.findall(".//Abstract/AbstractText")).strip()
            if title:
                snippet = abstract[:700] if abstract else journal
                src = f"PubMed / {journal}" if journal else "PubMed"
                results.append({"title": title, "snippet": snippet, "source": src,
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
    except Exception:
        pass
    return results[:count]


def search_arxiv(query, count=3):
    """arXiv 에서 관련 논문(제목+초록) 검색."""
    results = []
    try:
        r = requests.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{query}", "start": 0, "max_results": count, "sortBy": "relevance"},
            headers=UA, timeout=TIMEOUT,
        )
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.content)
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", "", ns) or "").replace(NL, " ").strip()
            summary = (entry.findtext("a:summary", "", ns) or "").replace(NL, " ").strip()
            link = (entry.findtext("a:id", "", ns) or "").strip()
            if title:
                results.append({"title": title, "snippet": summary[:700], "source": "arXiv", "url": link})
    except Exception:
        pass
    return results[:count]


def search_semantic_scholar(query, count=3):
    """Semantic Scholar 에서 관련 논문(제목+초록) 검색."""
    results = []
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": count,
                    "fields": "title,abstract,year,venue,citationCount,paperId"},
            headers=UA, timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return []
        for p in r.json().get("data", []):
            title = (p.get("title") or "").strip()
            abstract = (p.get("abstract") or "").strip()
            venue = (p.get("venue") or "").strip()
            year = p.get("year") or ""
            pid = p.get("paperId") or ""
            if title:
                src = f"Semantic Scholar / {venue} {year}".strip()
                results.append({"title": title, "snippet": abstract[:700], "source": src,
                                "url": f"https://www.semanticscholar.org/paper/{pid}"})
    except Exception:
        pass
    return results[:count]


def search_authoritative(keywords, topic="auto", count=3):
    """
    주제에 맞춰 신뢰 출처에서 자료를 검색·병합·중복제거.
    키워드를 개별 영문 검색어로 변환해 각각 검색하므로 회수율(recall)이 높음.
    topic: 'medical' | 'academic' | 'auto'
    """
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()] or [keywords]
    en_terms = _translate_keywords(", ".join(kw_list))
    results = []
    per = max(1, (count // max(1, len(en_terms))) + 1)
    for term in en_terms[:3]:
        if topic in ("medical", "auto"):
            results += search_pubmed(term, per)
        if topic in ("academic", "auto"):
            results += search_semantic_scholar(term, per)
            results += search_arxiv(term, per)
    seen = set()
    unique = []
    for r in results:
        key = r["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[: count * 2]


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "오십견 어깨 통증"
    topic = sys.argv[2] if len(sys.argv) > 2 else "auto"
    print(f"query keywords: {kw} (topic={topic})")
    for r in search_authoritative(kw, topic=topic, count=2):
        print(f"  [{r['source']}] {r['title'][:70]}")
        print(f"     {r['snippet'][:120]}")
