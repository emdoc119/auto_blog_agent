# 2026-08-08 네이버 표 발행 실험

## 변경

- `auto_post.py`에서 잘 형성된 Markdown 표를 명시적 HTML `<table><thead><tbody>`로 변환.
- 셀 테두리·패딩·폭을 inline style로 지정해 SmartEditor 클립보드 붙여넣기 시 표 구조 보존.
- `tests/test_auto_post_formatting.py` 추가.

## 실전 검증

- 예약 글 384번 `당뇨초기증상 조기에 잡고, 면역·균형을 되찾는 법`을 시험 발행.
- DB 상태: `published`, retry_count 0.
- 네이버 RSS에서 제목 확인.
- 실제 게시 페이지에서 `<table>` 15개와 표 셀 텍스트(`소변 횟수`, `당뇨초기증상 의심 신호`) 확인.
- 전체 테스트 24개 통과.

## 남은 제한

- 표가 아닌 일반 텍스트 형태로 생성된 malformed table은 자동 변환하지 않고 원문 보존.
- 4열 이상·긴 문장의 모바일 가독성은 별도 카드형 fallback이 필요할 수 있음.
