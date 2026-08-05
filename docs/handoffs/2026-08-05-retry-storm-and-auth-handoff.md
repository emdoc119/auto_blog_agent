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
- Commits: `3d0b285` fix: atomic pending claim and growing backoff stop retry storm / `512bfd0` docs: refresh handoff (브랜치 `codex/retry-storm-auth-recovery`, 이후 문서 갱신은 브랜치 HEAD) / 베이스: `9a1eb3f`
- Runtime gate: (a) `/api/status` 200 ✓ (b) 동일 post 반복 재시작 소멸 ✓ (c) pending 356/357/358 등 중복 재시도 없이 published 전진 ✓ (d) 353/354/355 발행 성공 ✓ (2026-08-05 19:25 KST 검증).
- Test baseline: 21/21 통과 (`PYTHONPATH=. ../venv/bin/python -B -m unittest discover -s tests -v`). pytest는 미설치라 unittest 사용.
- Runtime health: LaunchAgent `com.blogagent.dashboard` 수정 코드 반영 재시작 완료(점검 시 pid 94340), `/api/status` HTTP 200 확인. LAN 주소 `http://192.168.0.9:5001/` (DHCP 변동 가능). 샌드박스 내 curl/launchctl은 제한이라 검증은 escalation 필요.
- Active deployment path: 동일 디렉터리를 LaunchAgent가 직접 서빙. venv는 `../venv` (Python 3.9). stdout 블록 버퍼링으로 `scheduler_run.log`는 지연 기록 — 즉시 확인은 DB `logs` 테이블.
- DB 상태 (`blog_agent_v2.db`):
  - accounts: naver = `active` (2026-08-05 사용자가 보안 추가 확인 완료, `login_naver.py`가 세션 저장·계정 재활성화 수행)
  - posts: published 87 (353~358 발행), 남은 pending 백로그 순차 처리 중 (동시 2건 상한), cancelled 68
  - 세션이 다시 만료되면 계정이 정지되고 선점 쿼리도 자연스럽게 멈춤.
- Qwen 설정: `QWEN_MODEL=qwen3.6-flash`, `QWEN_STRONG_MODEL=qwen3.7-plus`, base URL은 Alibaba token-plan compatible-mode. 키는 `.env`(Git 제외)에 저장. 과거 `.env.md` 노출 건으로 로테이션 권고.

## Known Issues

1. (해결) 재시도 폭주: 커밋 `3d0b285`로 원자 선점·진행 중 가드·동시 상한·백오프 성장 적용, 회귀 테스트 7건 추가. 재발 여부만 아래 게이트 (c)~(d)로 확인.
2. (부분 해결) 평문 키 파일: `.env.md` 삭제 완료. 남은 조치: Alibaba 콘솔에서 Qwen 키 로테이션 후 `.env` 갱신(사용자 작업).
3. (해결) 네이버 보안 확인: 2026-08-05 사용자 완료, 계정 `active`, 세션 저장. 재만료 시 Jarvis 알림 후 동일 절차 반복.
4. 샌드박스 제약: `.git` 쓰기·launchctl·localhost curl은 escalation 필요. 이번 세션에서 launchctl list/kickstart, 헤드리스/headed 로그인, 커밋 승인 이력 있음.
5. 기존 잔여: Python 3.9 EOL/LibreSSL 경고, 대시보드 무인증 LAN 노출 (이번 범위 외, PROJECT_STATUS에 유지).

## Next Task

- Objective: (1) Qwen 키 로테이션 확인(사용자: Alibaba 콘솔에서 재발급 → `.env` 갱신. llm.py가 mtime 감지로 자동 반영) → (2) 남은 pending 백로그가 폭주 없이 소화되는지 확인.
- Monitoring: DB `posts`/`logs`에서 단방향 전진 확인. 특정 글이 반복 실패하면 `retry_after` 성장(15→30→60→120→240→360분)으로 백오프 적용을 확인. 동일 post 반복 집힘이 재발하면 `pipeline_state.claim_pending_post`와 회귀 테스트를 대조.
- Allowed files: `docs/`. 코드 수정 불필요 — 새 오류가 발견되면 먼저 사용자와 상의.
- Required tests: 코드 변경 시에만 전체: `PYTHONPATH=. ../venv/bin/python -B -m unittest discover -s tests -v`.
- Runtime gate: (a)~(d) 전부 통과 (Current State 참조). 새 변경이 있으면 동일 기준으로 재검증.
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
