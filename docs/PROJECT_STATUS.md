# Blog Agent — 프로젝트 상태

> 마지막 갱신: 2026-07-29

## 현재 상태

- 네이버 블로그 자동 발행 에이전트. Flask 대시보드(포트 5001) + 백그라운드 스케줄러.
- macOS LaunchAgent(`com.blogagent.dashboard`)로 영속 실행 (로그인 시 자동 시작, 크래시 시 재시작).
- 2026-07-29 기준 서비스 정상 가동 중, 일일 글 생성/발행 재개됨.

## 아키텍처 (파이프라인)

`Orchestrator`가 글마다 다음을 조율:
`(Trend, 선택) → Researcher(신뢰출처 PubMed/arXiv/S2 + 네이버) → Writer(Qwen 작성 + Pexels 실사 사진 인라인) → Editor(루브릭 편집) → 품질 점수화/자동개선(임계값 75, 최대 2회) → SEO 태그 → DB 저장(scheduled)`

발행은 `app.py` 스케줄러가 예약 시각(09·13·18시)에 `Publisher → auto_post.py`(Playwright, 네이버 SmartEditor) 호출.
일일 루틴: 통계 수집 + 성과 기반 전략 갱신(Feedback) + 오늘/내일 글 생성.

## 주요 모듈

- `llm.py` — 통합 LLM (Qwen 1순위, Gemini 폴백, 재시도/사용량 기록)
- `sources.py` — PubMed/arXiv/Semantic Scholar (무료 무키)
- `image_source.py` — Pexels 저작권 프리 사진
- `seo.py` — 검색 태그 자동 생성
- `agents/editor.py` — 품질 편집/점수화/개선
- `agents/orchestrator.py` — 파이프라인 조율
- `auto_post.py` — 네이버 실제 발행

## 알려진 문제 / 다음 우선순위

1. **[긴급] Qwen(Token Plan) API 키 무효(401)** — 현재 Gemini 폴백으로 동작(글당 ~15초 재시도 지연). 키 갱신 필요.
2. `auto_post.py`는 발행 버튼 실패/URL 미변경 때도 종료코드 0을 반환 → 허위 `published` 가능. 실제 발행 완료 검증 필요.
3. Flask 대시보드가 인증 없이 `0.0.0.0` 노출, 고정 secret key, 평문 credentials — 인증/CSRF/비밀 외부화 필요.
4. Publisher 비정상 종료 경로가 `_mark_error()`를 안 불러 `publishing` 고착 가능.
5. 통계 수집 실패 시 임의 방문자 수 생성 → 피드백 데이터 오염. 제거 필요.
6. 제목 A/B 테스트 미구현 (조회수 데이터 축적 후 진행).

## 운영 메모

- 서비스 재시작: `launchctl kickstart -k gui/$(id -u)/com.blogagent.dashboard`
- 네이버 세션 만료 시: `../venv/bin/python login_naver.py`
- 기능 플래그(.env): ENABLE_EDITOR, ENABLE_TREND, ENABLE_QUALITY_SCORE, ENABLE_SEO, QUALITY_THRESHOLD, MAX_QUALITY_ATTEMPTS, EDITOR_TIER
- 비밀키(.env, gitignore): DASHSCOPE_API_KEY, GEMINI_API_KEY, DASHSCOPE_BASE_URL, PEXELS_API_KEY
