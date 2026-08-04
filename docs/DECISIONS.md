# 주요 설계 결정

## 2026-08-05 — 네이버 자격증명은 `.env`가 아닌 macOS Keychain에 저장

- 결정: 네이버 아이디와 비밀번호는 macOS Keychain에만 저장하고, Playwright 세션 만료 시 제한적으로 자동 로그인에 사용한다.
- 이유: `.env`는 Git에서 제외해도 평문 파일이며 백업·로그·권한 오류로 노출될 수 있다. Security Framework 직접 호출은 비밀번호를 파일, DB, 셸 명령행에 남기지 않는다.
- 고려한 대안:
  - `.env`: 구현은 단순하지만 평문 장기 보관이라 제외.
  - 항상 수동 로그인: 안전하지만 장기 자동화의 병목이 커서 제외.
  - Naver 공식 API: 현재 블로그 SmartEditor 발행과 세션 갱신을 대체하지 못해 제외.
- 영향:
  - 세션 만료 시 백그라운드 자동 로그인을 시도한다.
  - CAPTCHA, 2단계 인증, 계정 보호조치는 우회하거나 반복 시도하지 않고 `manual_reauth_required`로 전환한다.
  - 계정이 `reauth_required`인 동안 생성과 발행을 함께 정지한다.

## 2026-08-05 — 수동 개입 알림은 Jarvis의 단일 Telegram 채널 사용

- 결정: Blog Agent는 Jarvis Telegram 봇의 단일 허용 사용자에게 상태 전환 알림만 보낸다.
- 보안: Jarvis 토큰과 대상 ID는 Blog Agent `.env`에 복사하지 않고 macOS Keychain에 이관한다.
- 중복 방지: 동일 상태는 12시간 안에 다시 보내지 않으며 `manual_required → resolved`처럼 상태가 바뀔 때 즉시 알린다.
- 장애 격리: Telegram 전송 실패가 로그인 복구, 글 생성 또는 발행을 실패시키지 않는다.
- 범위: 우선 네이버 수동 인증 필요와 정상 복구를 알리며, 향후 다른 치명적 운영 중단에도 같은 상태 API를 사용한다.
