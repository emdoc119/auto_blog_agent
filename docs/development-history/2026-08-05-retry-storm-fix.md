# 2026-08-05 재시도 폭주 수정 + 키 위생 정리

## 증상

- Qwen 주간 한도 소진 기간 동안 pending 글 20여 개가 약 15분 주기로 계속 재실행됨.
- retry_count 최대 56회. 매 재시도마다 키워드 검색과 LLM 호출 시도가 반복됨.
- `.env.md`에 Qwen API 키 평문 파일 존재(Git 미추적이지만 디스크 상존, 도구 출력 노출 이력).
- 네이버 세션 만료로 계정 `manual_reauth_required`, 생성·발행 정지.

## 원인

- `pipeline_state.defer_post`가 제공자 `retry_after`(회로 재오픈·리셋 시각)를 지수 백오프 대신 그대로 사용 → 반복 실패에도 백오프가 성장하지 않음.
- 스케줄러가 SELECT 후 UPDATE 두 단계로 pending을 집어 중복 선점 가능성이 있었고, 진행 중 가드와 동시 파이프라인 상한이 없었음.

## 변경

- `pipeline_state.claim_pending_post`: 후보 SELECT 후 `status='pending'` 조건부 UPDATE + rowcount 확인으로 원자 선점. 프로세스 내 진행 중 포스트 집합과 락으로 중복 집합 차단.
- `pipeline_state.release_pipeline`, `active_pipeline_count`, `MAX_CONCURRENT_PIPELINES=2` 추가. 스케줄러가 띄우는 스레드는 finally에서 슬롯 해제.
- `defer_post`: 지수 백오프와 제공자 재시도 시각 중 더 늦은 시각 선택(`max`).
- `app.py background_scheduler`: 선점 함수 사용, 상한 초과 시 스킵, 선점 직후 프로젝트 비활성이면 pending 복귀 + 슬롯 해제.
- `.env.md` 삭제. 키는 `.env`(Git 제외)에만 존재. Alibaba 콘솔 키 로테이션 권고.
- 고정 날짜로 거짓 실패하던 `test_qwen_reset_timestamp_is_parsed`를 동적 미래 시각 검증으로 수정.

## 검증

- 테스트 21개 전부 통과(기존 14 + 신규 7): 원자 선점, 백오프 중 미재집합, 진행 중 가드, 동시 선점 중복 없음, 백오프 성장, 제공자 리셋 존중.
- LaunchAgent 재시작 후 `/api/status` HTTP 200. pending/scheduled 건수 변동 없음. 중복 재시도 로그 없음.
- 게이트 (c) pending 전진과 (d) 353/354/355 발행은 네이버 보안 확인 완료 후 검증 예정.

## 남은 위험

- 네이버 보안 추가 확인은 사용자 수동 완료 필요. 그 전까지 생성·발행 정지 지속.
- Qwen 키 로테이션 전까지 과거 노출된 키가 유효.
- stdout 블록 버퍼링으로 scheduler_run.log 기록이 지연될 수 있어 즉시 확인은 DB logs 테이블 사용.
