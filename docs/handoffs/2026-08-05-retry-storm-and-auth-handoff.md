# Qwen 3.8 Max Preview Handoff — 네이버 로그인 완료 + 런타임 게이트 검증

> 갱신: 2026-08-05 (KST), Qwen 3.8 Max Preview 세션 작성. 재시도 폭주 수정·`.env.md` 삭제·서비스 재시작까지 완료.

## Source of Truth

- Canonical repository: `/Users/choo/.gemini/antigravity/scratch/blog_agent`
- Active branch/worktree: `main` (clean, `origin/main`과 동기화, HEAD `9a1eb3f`)
- Remote: `origin`
- Status document: `docs/PROJECT_STATUS.md`
- Plan: 이 핸드오프가 계획 (별도 plan 파일 없음)
- Relevant history: `docs/development-history/2026-08-02-resilience-recovery.md` (retry_after/백오프 도입 배경)

## Model Lock

- Main: `Qwen 3.8 Max Preview`
- Subagents: exact same displayed model and canonical runtime ID (`alibaba-token-plan-intl/qwen3.8-max-preview`, spawn 시 표시명 `Qwen 3.8 Max Preview` 확인 필수)
- Fallback: none
- Failure behavior: record `BLOCKED` and stop

## Current State

- Last completed task: 재시도 폭주 수정 구현·배포 완료(2026-08-05, Qwen 3.8 Max Preview 메인 세션). `pipeline_state.claim_pending_post` 원자 선점 + 진행 중 가드 + 동시 파이프라인 상한(2), `defer_post`는 지수 백오프와 제공자 재시도 시각 중 더 늦은 시각 선택. `.env.md` 삭제 완료. 서비스 재시작·헬스 확인 완료.
- Commits: `3d0b285` fix: atomic pending claim and growing backoff stop retry storm (브랜치 `codex/retry-storm-auth-recovery`) / 베이스: `9a1eb3f` fix: report open LLM circuit reasons
- Test baseline: 21/21 통과 (`PYTHONPATH=. ../venv/bin/python -B -m unittest discover -s tests -v`). pytest는 미설치라 unittest 사용.
- Runtime health: LaunchAgent `com.blogagent.dashboard` 수정 코드 반영 재시작 완료(점검 시 pid 94340), `/api/status` HTTP 200 확인. LAN 주소 `http://192.168.0.9:5001/` (DHCP 변동 가능). 샌드박스 내 curl/launchctl은 제한이라 검증은 escalation 필요.
- Active deployment path: 동일 디렉터리를 LaunchAgent가 직접 서빙. venv는 `../venv` (Python 3.9). stdout 블록 버퍼링으로 `scheduler_run.log`는 지연 기록 — 즉시 확인은 DB `logs` 테이블.
- DB 상태 (`blog_agent_v2.db`):
  - accounts: naver = `manual_reauth_required` (네이버 "보안 추가 확인" 대기. headless 자동 로그인 시도 결과 manual=True)
  - posts: published 81, scheduled 3 (353/354/355), pending 17 (retry_count 최대 56, 수정된 백오프 적용 대기), cancelled 68
  - 계정 비활성 동안 선점 쿼리가 accounts를 JOIN하므로 pending 처리는 자연스럽게 정지 상태.
- Qwen 설정: `QWEN_MODEL=qwen3.6-flash`, `QWEN_STRONG_MODEL=qwen3.7-plus`, base URL은 Alibaba token-plan compatible-mode. 키는 `.env`(Git 제외)에 저장. 과거 `.env.md` 노출 건으로 로테이션 권고.

## Known Issues

1. (해결) 재시도 폭주: 커밋 `3d0b285`로 원자 선점·진행 중 가드·동시 상한·백오프 성장 적용, 회귀 테스트 7건 추가. 재발 여부만 아래 게이트 (c)~(d)로 확인.
2. (부분 해결) 평문 키 파일: `.env.md` 삭제 완료. 남은 조치: Alibaba 콘솔에서 Qwen 키 로테이션 후 `.env` 갱신(사용자 작업).
3. 네이버 보안 확인 대기: 계정 `manual_reauth_required`. 2026-08-05 `attempt_auto_login(headless=True)` 결과 "네이버 보안 추가 확인". headed `login_naver.py` 실행 1회는 10분 제한 타임아웃. 성공 시 스크립트가 `naver_state.json` 저장 + `activate_naver_accounts()` 수행.
4. 샌드박스 제약: `.git` 쓰기·launchctl·localhost curl은 escalation 필요. 이번 세션에서 launchctl list/kickstart, 헤드리스/headed 로그인, 커밋 승인 이력 있음.
5. 기존 잔여: Python 3.9 EOL/LibreSSL 경고, 대시보드 무인증 LAN 노출 (이번 범위 외, PROJECT_STATUS에 유지).

## Next Task

- Objective: (1) 네이버 로그인 완료(사용자 보안 확인) → (2) 계정 재활성화 확인 → (3) 런타임 게이트 (c)(d) 검증 → (4) Qwen 키 로테이션 완료 확인. 순서 준수.
- Login procedure: `cd /Users/choo/.gemini/antigravity/scratch/blog_agent && ../venv/bin/python -B login_naver.py` (headed, escalation 필요). 키체인 자동 입력 후 네이버 보안 추가 확인만 사용자가 완료. 성공 시 스크립트가 `naver_state.json` 저장 + 계정 재활성화 처리. 타임아웃/실패 시 사용자 준비 후 재실행. 자동 우회 금지.
- Allowed files: `docs/` (상태·핸드오프 갱신). 코드 수정 불필요 — 로그인 중 새 오류가 발견돼도 `naver_auth.py` 수정 전에 사용자와 상의.
- Required tests: 로그인만 수행하고 코드를 바꾸지 않으면 생략 가능. 코드를 변경하면 `PYTHONPATH=. ../venv/bin/python -B -m unittest discover -s tests -v` 전체.
- Runtime gate: (a) `/api/status` HTTP 200 ✓, (b) 재시작 후 동일 post 반복 재시작 소멸 ✓ (계정 비활성으로 선점 0건). 남은 게이트: (c) pending 1건이 중복 재시도 없이 scheduled/published로 전진, (d) 353/354/355 발행 진행. 확인은 DB `posts`/`logs` 테이블 중심, 필요 시 escalation curl.
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
