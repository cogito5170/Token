# ADR-0005 텔레메트리 수집

- 상태: 채택
- 결정: 수집 단위는 "업로드 1 개 = 수집 작업 1 개". 워커가 형식 감지 → 기존 파서 → 비밀값 제거 → `UsageCall` 정규화 → 중복 제거 → `usage.load_calls` 순서로 처리한다(data-model.md 4 절). 모든 원천은 먼저 **L0 이벤트(l0-telemetry/1)** 로 바뀐 뒤 정규화된다: Claude Code 는 `from_cc_jsonl`, ga 는 이미 L0, 공급자 내보내기는 행 → usage dict → `l0_usage`.
- 이유: L0 를 공통 중간 형식으로 두면 파서가 l0-telemetry 한 곳에 모이고, 나중의 OTel · ga runner 도 같은 길을 쓴다. `reported_null` 규칙(모르는 값은 0 이 아니라 없음)을 그대로 물려받는다.
- 결과:
  - 같은 파일 재업로드는 `dedupe_key` 로 멱등.
  - 시각이 없는 L0(`at` null)는 업로드 시각 + `time_basis='ingested'` 로 표시하고 화면에 알린다.
  - 프롬프트 본문은 기본적으로 버린다.
  - (나중) 공급자 API 자동 연동은 같은 파이프라인에 `sources.kind='anthropic_api'` 로 들어오는 주기 작업이다.
