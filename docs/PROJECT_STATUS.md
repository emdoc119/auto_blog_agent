# Blog Agent — 프로젝트 상태

> 마지막 갱신: 2026-08-05

## 현재 상태

- 네이버 블로그 자동 발행 에이전트. Flask 대시보드(포트 5001)와 백그라운드 스케줄러로 구성.
- macOS LaunchAgent(`com.blogagent.dashboard`)로 로그인 시 시작·장애 시 재시작.
- 서비스 HTTP 200 확인. 현재 LAN 주소는 `http://192.168.0.9:5001/`.
- Qwen은 한도·인증 오류 때 회로를 즉시 차단하고 Gemini로 폴백함.
- 네이버 계정은 `active` (2026-08-05 보안 추가 확인 완료 후 복구). 생성·발행 재개.
- 2026-08-05 재시도 폭주 수정 완료: 원자적 선점, 진행 중 가드, 동시 파이프라인 상한, 지수 백오프 우선.
- published 87건(353~358 포함). 남은 pending 백로그는 수정된 선점·백오프로 순차 처리 중. 과거 밀린 68건은 `cancelled` 보존.

## 파이프라인

`Researcher → Writer(Qwen 우선/Gemini 폴백 + Pexels) → 품질 채점 → 기준 미달만 Editor 개선 → SEO → scheduled`

- 글별 경쟁사 Trend 호출은 기본 비활성화하여 토큰·시간 사용을 줄임.
- 모든 LLM 제공자가 실패하면 `error`로 고정하지 않고 `pending + retry_after`로 지수 백오프하되, 제공자 재시도 시각과 비교해 더 늦은 시각을 적용.
- 스케줄러는 pending 포스트를 조건부 UPDATE로 원자 선점하고, 진행 중 포스트 중복 집합 가드와 동시 파이프라인 2건 상한으로 재시도 폭주를 방지.
- 프로세스 재시작 시 `researching/writing/editing`은 `pending`, `publishing`은 `scheduled`로 복구.
- Writer 초안은 `editing`으로 유지하고 품질·SEO 완료 후에만 `scheduled`로 전환.
- 품질 점수가 없거나 기준 미달이면 발행하지 않고 백오프 재처리.
- 발행은 URL 전환 또는 네이버 RSS에서 제목을 확인한 경우에만 `published` 처리.
- 카테고리 선택 실패는 잘못된 게시판에 올리지 않고 발행 전체를 재시도.
- 네이버 세션 만료 시 계정을 `reauth_required`로 일시 정지하고 생성·발행을 함께 멈춤.
- macOS Keychain 자격증명이 있으면 자동 로그인 후 세션·계정을 복구하며 CAPTCHA·2단계 인증은 반복하지 않고 수동 확인으로 전환.
- 수동 확인 전환과 정상 복구는 Jarvis Telegram으로 한 번만 알리며 같은 상태는 12시간 동안 중복 억제.

## 프로젝트 일정

- 건강하게 100세: 하루 3회
- AI 논문 작성: 하루 3회
- 위고비/마운자로: 하루 3회
- 통증 치료 가이드: 하루 1회

## 알려진 문제 / 다음 우선순위

1. 네이버 계정 `active` 복구 완료(2026-08-05). 세션 재만료 시 Jarvis 알림 후 `../venv/bin/python login_naver.py` headed 실행으로 수동 확인.
2. Qwen API 키 로테이션 권장: 과거 `.env.md` 평문 노출 이력(파일은 2026-08-05 삭제). Alibaba 콘솔에서 키 재발급 후 `.env`만 갱신.
3. Python 3.9 EOL 및 LibreSSL 경고가 있어 Python 3.11+ 런타임으로 이전 권장.
4. 대시보드가 LAN 전체(`0.0.0.0`)에 인증 없이 노출됨. Basic Auth/CSRF 적용 필요.
5. LAN IP가 DHCP로 바뀌므로 고정 주소 또는 로컬 호스트명 도입 검토.

## 운영 메모

- 서비스 재시작: `launchctl kickstart -k gui/$(id -u)/com.blogagent.dashboard`
- 네이버 세션 갱신: `../venv/bin/python login_naver.py`
- 자동 로그인 자격증명 등록(GUI): `../venv/bin/python -B setup_naver_credentials.py --gui`
- Jarvis 알림 설정: `../venv/bin/python -B setup_jarvis_notifications.py`
- 주요 로그: `scheduler_run.log`, DB `logs` 테이블
- API 키는 Git 제외 `.env`, 네이버·Jarvis 인증정보는 macOS Keychain에 저장하며 로그·문서에 값을 기록하지 않음.
- 스케줄러 로그는 stdout 블록 버퍼링으로 지연 기록될 수 있음. 즉시 확인은 DB `logs` 테이블 사용.
