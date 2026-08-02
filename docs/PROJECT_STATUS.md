# Blog Agent — 프로젝트 상태

> 마지막 갱신: 2026-08-02

## 현재 상태

- 네이버 블로그 자동 발행 에이전트. Flask 대시보드(포트 5001)와 백그라운드 스케줄러로 구성.
- macOS LaunchAgent(`com.blogagent.dashboard`)로 로그인 시 시작·장애 시 재시작.
- 서비스 HTTP 200 확인. 현재 LAN 주소는 `http://192.168.0.9:5001/`.
- Qwen Token Plan 주간 한도는 2026-08-05 06:12 UTC까지 소진 상태. Qwen 회로를 즉시 차단하고 Gemini로 폴백하도록 복구함.
- 과거 밀린 작업 38건은 데이터는 보존한 채 `cancelled`. 오늘·내일 작업은 복구했으며 현재 네이버 재로그인 전까지 안전 정지.

## 파이프라인

`Researcher → Writer(Qwen 우선/Gemini 폴백 + Pexels) → 품질 채점 → 기준 미달만 Editor 개선 → SEO → scheduled`

- 글별 경쟁사 Trend 호출은 기본 비활성화하여 토큰·시간 사용을 줄임.
- 모든 LLM 제공자가 실패하면 `error`로 고정하지 않고 `pending + retry_after`로 지수 백오프.
- 프로세스 재시작 시 `researching/writing/editing`은 `pending`, `publishing`은 `scheduled`로 복구.
- Writer 초안은 `editing`으로 유지하고 품질·SEO 완료 후에만 `scheduled`로 전환.
- 발행은 URL 전환 또는 네이버 RSS에서 제목을 확인한 경우에만 `published` 처리.
- 카테고리 선택 실패는 잘못된 게시판에 올리지 않고 발행 전체를 재시도.
- 네이버 세션 만료 시 계정을 `reauth_required`로 일시 정지하고 생성·발행을 함께 멈춘 뒤 로그인 갱신 후 자동 재개.

## 프로젝트 일정

- 건강하게 100세: 하루 3회
- AI 논문 작성: 하루 3회
- 위고비/마운자로: 하루 3회
- 통증 치료 가이드: 하루 1회

## 알려진 문제 / 다음 우선순위

1. Qwen 주간 Token Plan 한도가 현재 소진됨. 리셋 전까지 Gemini 폴백 사용.
2. Python 3.9 EOL 및 LibreSSL 경고가 있어 Python 3.11+ 런타임으로 이전 권장.
3. 대시보드가 LAN 전체(`0.0.0.0`)에 인증 없이 노출됨. Basic Auth/CSRF 적용 필요.
4. 현재 네이버 로그인 세션 갱신이 필요함. `login_naver.py` 성공 시 대기 발행 자동 재개.
5. LAN IP가 DHCP로 바뀌므로 고정 주소 또는 로컬 호스트명 도입 검토.

## 운영 메모

- 서비스 재시작: `launchctl kickstart -k gui/$(id -u)/com.blogagent.dashboard`
- 네이버 세션 갱신: `../venv/bin/python login_naver.py`
- 주요 로그: `scheduler_run.log`, DB `logs` 테이블
- 비밀키는 Git에서 제외된 `.env`에만 저장하며 로그·문서에 값을 기록하지 않음.
