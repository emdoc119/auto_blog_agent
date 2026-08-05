# Qwen 3.8 Max Preview Handoff — 재시도 폭주 수정 + 파일 정리 + 네이버 로그인 복구

> 생성: 2026-08-05 (KST), 직전 세션(GPT-5, Model Lock 미충족으로 편집 중단) 작성

## Source of Truth

- Canonical repository: `/Users/choo/.gemini/antigravity/scratch/blog_agent`
- Active branch/worktree: `main` (clean, `origin/main`과 동기화, HEAD `9a1eb3f`)
- Remote: `origin`
- Status document: `docs/PROJECT_STATUS.md`
- Plan: 이 핸드오프가 계획 (별도 plan 파일 없음)
- Relevant history: `docs/development-history/2026-08-02-resilience-recovery.md` (retry_after/백오프 도입 배경)

## Model Lock

- Main: `Qwen 3.8 Max Preview`
- Subagents: exact same displayed model and canonical runtime ID (`alibaba-token-plan-intl/qwen38-max-preview` 계열, spawn 시 표시명 `Qwen 3.8 Max Preview` 확인 필수)
- Fallback: none
- Failure behavior: record `BLOCKED` and stop

## Current State

- Last completed task: 진단 완료. Qwen 주간 quota가 08-05 06:12 UTC에 리셋된 뒤 `qwen3.6-flash` 호출 6회 성공(15:13~15:15 KST), 글 353/354/355가 품질 게이트(86/84/82점) 통과 후 `scheduled` 전환 확인.
- Commits: `9a1eb3f` fix: report open LLM circuit reasons / `6ef16b6` feat: Jarvis alerts / `ea86740` feat: secure Naver session auto-refresh
- Test baseline: 이번 세션에서 미실행. `tests/test_resilience.py` 존재. 재개 시 먼저 `../venv/bin/python -m pytest tests/ -q` (또는 unittest)로 베이스라인 확보.
- Runtime health: LaunchAgent `com.blogagent.dashboard` running (점검 시 pid 43664), `*:5001` LISTEN 확인. LAN 주소 `http://192.168.0.9:5001/` (DHCP로 변동될 수 있음). 샌드박스 내 curl은 네트워크 제한으로 실패했으므로 브라우저 또는 샌드박스 밖에서 HTTP 200 검증할 것.
- Active deployment path: 동일 디렉터리를 LaunchAgent가 직접 서빙. venv는 `../venv` (Python 3.9).
- DB 상태 (`blog_agent_v2.db`):
  - accounts: naver = `manual_reauth_required` (세션 만료로 발행 정지)
  - posts: published 81, scheduled 3 (353/354/355), pending 17 (retry_count 최대 56), cancelled 68
  - 353은 발행 시도 중 "Session expired while opening editor"로 실패, retry_after `2026-08-05 15:44:28`
- Qwen 설정: `QWEN_MODEL=qwen3.6-flash`, `QWEN_STRONG_MODEL=qwen3.7-plus`, base URL은 Alibaba token-plan compatible-mode. 키는 `.env`(Git 제외)에 저장.

## Known Issues

1. 재시도 폭주 (핵심): `app.py background_scheduler`가 매분 pending 1건을 골라 스레드를 띄우는데, 실패 시 `pipeline_state.defer_post`가 백오프를 잡아도 같은 글이 다시 집혀 매분 재실행됨. 로그에 동일 post "파이프라인 재시작"이 매분 반복, retry_count 56회 도달. 수정 대상: 원자적 선점(claim), 진행 중 post 중복 집합 가드, 제공자 리셋 시각 존중 백오프, 동시 파이프라인 스레드 상한.
2. 평문 키 파일: `.env.md`에 Qwen API 키 평문 존재(Git 미추적이나 디스크 상존). 직전 진단 중 도구 출력에 키가 노출된 이력 있음 → 파일 삭제 + 사용자에게 Alibaba 콘솔에서 키 로테이션 권고. `.gitignore`는 `.env*`를 이미 커버함.
3. 네이버 세션 만료: 계정 `manual_reauth_required`. 스케줄러 자동 재로그인은 `reauth_required` 상태만 트리거하므로(설계 의도) 수동 확인 필요. `naver_auth.attempt_auto_login(headless=True)` 먼저 시도하고, CAPTCHA/2FA 등 보안 확인이 걸리면 `../venv/bin/python login_naver.py`를 headed로 띄워 사용자가 확인만 완료하게 한 뒤 `activate_naver_accounts()`.
4. 샌드박스 제약: 이 저장소 `.git`은 샌드박스에서 읽기 전용 → git 쓰기 작업은 escalation 필요. 자동 승인 검토가 사용량 한도로 거부된 이력 있음(2026-08-09 재시도 가능 메시지). 커밋 시점에 사용자에게 명시적 승인을 요청할 것.
5. 기존 잔여: Python 3.9 EOL/LibreSSL 경고, 대시보드 무인증 LAN 노출 (이번 범위 외, PROJECT_STATUS에 유지).

## Next Task

- Objective: (1) 재시도 폭주 수정 → (2) `.env.md` 제거 및 키 위생 정리 → (3) 네이버 로그인 복구 → (4) 서비스 재시작·검증 → (5) 문서/커밋. 순서 준수.
- Allowed files: `app.py`, `pipeline_state.py`, `tests/` (신규 테스트 추가), `docs/`, `.env.md` (삭제), 필요 최소한으로 `naver_auth.py`. 그 외 파일 수정 금지.
- Required tests: `tests/test_resilience.py` 전부 + 신규 테스트: pending 원자적 선점(같은 post 동시 2회 집합 불가), 백오프 중 post 미재집합.
- Runtime gate: 서비스 재시작 후 (a) `/api/status` HTTP 200, (b) `scheduler_run.log`에 동일 post 반복 재시작 소멸, (c) pending 1건이 중복 재시도 없이 scheduled/published로 전진, (d) 네이버 로그인 성공 시 353/354/355 발행 진행.
- Rollback: 변경은 `codex/retry-storm-auth-recovery` 브랜치에만. 문제 시 `git switch main` 후 `launchctl kickstart -k gui/$(id -u)/com.blogagent.dashboard`.

## Delegation

- 서브에이전트 위임 가능: 재시도 폭주 수정 + 테스트 작성 1건 (파일 소유: `app.py`, `pipeline_state.py`, `tests/test_scheduler_claim.py`). `fork_turns="none"`, self-contained brief, reasoning `high`(동시성 포함이면 `xhigh`).
- 직렬 유지(메인 담당): 네이버 로그인 복구(브라우저/계정 상태 공유), `.env.md` 삭제, 서비스 재시작, 문서 갱신, 최종 검증과 커밋.

## Stop Conditions

- Exact model missing or unavailable
- Dirty-tree overlap with user changes
- Failed baseline tests
- Secret exposure suspicion (추가 노출 발견 시 즉시 중단·보고)
- Required merge, production write, or destructive action without approval
- 네이버 CAPTCHA/2FA: 자동 우회 금지, 사용자 수동 완료 대기
- Qwen API quota/인증 재실패: 타 모델 대체 금지, `BLOCKED` 기록 후 중단

## Start Prompt

Select Qwen 3.8 Max Preview as the main model, invoke `$qwen38-max-development`, read this handoff and `docs/PROJECT_STATUS.md`, then continue the Next Task without substituting any other model.
