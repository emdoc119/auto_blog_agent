# Blog Agent — 프로젝트 상태

> 마지막 갱신: 2026-08-05

## 현재 상태

- 네이버 블로그 자동 발행 에이전트. Flask 대시보드(포트 5001)와 백그라운드 스케줄러로 구성.
- macOS LaunchAgent(`com.blogagent.dashboard`)로 로그인 시 시작·장애 시 재시작.
- 서비스 HTTP 200 확인. 현재 LAN 주소는 `http://192.168.0.9:5001/`.
- Qwen은 한도·인증 오류 때 회로를 즉시 차단하고 Gemini로 폴백함.
- 네이버 계정은 현재 `active`. 오늘·내일 작업 20건을 품질 게이트를 거쳐 순차 재처리 중.
- 과거 밀린 작업 68건은 데이터는 보존한 채 `cancelled` 처리.

## 파이프라인

`Researcher → Writer(Qwen 우선/Gemini 폴백 + Pexels) → 품질 채점 → 기준 미달만 Editor 개선 → SEO → scheduled`

- 글별 경쟁사 Trend 호출은 기본 비활성화하여 토큰·시간 사용을 줄임.
- 모든 LLM 제공자가 실패하면 `error`로 고정하지 않고 `pending + retry_after`로 지수 백오프.
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

1. Python 3.9 EOL 및 LibreSSL 경고가 있어 Python 3.11+ 런타임으로 이전 권장.
2. 대시보드가 LAN 전체(`0.0.0.0`)에 인증 없이 노출됨. Basic Auth/CSRF 적용 필요.
3. CAPTCHA·2단계 인증 발생 시 `login_naver.py`로 수동 확인 필요하며 Jarvis가 알림.
4. LAN IP가 DHCP로 바뀌므로 고정 주소 또는 로컬 호스트명 도입 검토.

## 운영 메모

- 서비스 재시작: `launchctl kickstart -k gui/$(id -u)/com.blogagent.dashboard`
- 네이버 세션 갱신: `../venv/bin/python login_naver.py`
- 자동 로그인 자격증명 등록(GUI): `../venv/bin/python -B setup_naver_credentials.py --gui`
- Jarvis 알림 설정: `../venv/bin/python -B setup_jarvis_notifications.py`
- 주요 로그: `scheduler_run.log`, DB `logs` 테이블
- API 키는 Git 제외 `.env`, 네이버·Jarvis 인증정보는 macOS Keychain에 저장하며 로그·문서에 값을 기록하지 않음.
