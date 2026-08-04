# 2026-08-05 Jarvis 운영 알림 연동

## 목적

네이버 보안 확인처럼 자동화가 사람의 조치를 기다릴 때 대시보드를 계속 확인하지 않아도 Jarvis Telegram으로 알림을 받는다.

## 구현

- 기존 Jarvis Telegram 봇과 단일 허용 사용자를 확인해 Blog Agent Keychain에 안전하게 이관.
- `manual_reauth_required` 전환 시 경고 알림.
- 로그인 복구 및 계정 활성화 시 해결 알림.
- 이벤트 키·상태 기반 DB 중복 억제와 12시간 지속 장애 재알림.
- 알림 실패가 본 파이프라인에 영향을 주지 않는 best-effort 격리.
- 현재 수동 확인 대기 상태이면 설정 직후 실제 상태 알림 한 건 전송.

## 보안

- Telegram 토큰과 사용자 ID는 Git, `.env`, SQLite 로그에 저장하지 않는다.
- 발신 대상은 Jarvis에 이미 설정된 단일 허용 사용자로 고정한다.
- 실제 메시지에는 비밀번호, API 키, 원문 예외 전문을 포함하지 않는다.

## 검증

- Jarvis Docker API·bot-listener·worker 실행 상태 확인.
- Jarvis Telegram 전송 활성화, 토큰 존재, 허용 사용자 1명 확인.
- 단일 사용자 전송과 중복 억제 단위 테스트 추가.
