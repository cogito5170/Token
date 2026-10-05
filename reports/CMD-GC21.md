```ga
{"schema":"report/2","from":"ingestion-analytics","handled":[{"id":"CMD-GC21","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc21","sha":"cc3fd993bb02c7d62457060b612848589d5fc9bf"}],"tests":{"passed":17,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["usage.tests.test_usage.CostingTest.test_every_final_task_call_matches_quota_usd_within_one_micro_usd (all 213 ledger calls, <=1 micro-USD)","usage.tests.test_usage_pg (same on PostgreSQL 16)"]},{"id":"D2","state":"met","evidence":["usage.tests.test_usage.LoadTest.test_reload_is_idempotent_by_dedupe_key","usage.tests.test_usage_pg.test_cost_idempotent_reload_and_nulls"]},{"id":"D3","state":"met","evidence":["usage.tests.test_usage.CostingTest.test_nulls_stay_null","ChartTest.test_summary_carries_unit_and_provenance_and_coverage"]},{"id":"D4","state":"met","evidence":["ChartTest.test_summary_carries_unit_and_provenance_and_coverage","ChartTest.test_token_series","ChartTest.test_call_size_histogram_and_outliers","CompareTest","TaskPatchTest"]}]}
```

# CMD-GC21 보고: usage 도메인

## 한 일
- `pricing.py`: 정가 환산(nano-USD, 정수), 시드(FINAL_TASK 표: Haiku $1/$5, Sonnet $2/$10, 캐시 쓰기 ×1.25(1h ×2), 읽기 ×0.1). 가격은 `model_prices` 행이 원천이고 호출 행에 `price_version` 을 남긴다. 반올림은 집계에서 한 번만.
- `service.py`: `load_calls`(가격 계산 → 한 트랜잭션 적재, `(workspace, dedupe_key)` 멱등, 세션·작업 합계, `usage_daily` 재집계, `usage.calls.ingested` 발행), summary · 토큰 시계열(hour/day/week, group_by) · 호출 크기 히스토그램(log2 구간 + 임계 초과 이상치) · compare · calls/sessions/tasks 페이지 · 작업 PATCH(`usage.task.outcome_set`, 값이 바뀔 때만 발행).
- `pg_store.py`(PostgreSQL), `MemoryStore`(테스트), `api.py`(`load_calls`, `summary`, `calls`, `tasks`), `router.py`(/v1/models, /usage/*), `wiring.py`, `_identity.py`.
- 모든 시리즈·타일은 `unit` 과 `provenance` 를 가진다. 알 수 없는 값은 NULL(0 아님); cli 비용은 `coverage_permille`.

## 바뀐 파일
`backend/app/domains/usage/**` 만.

## 테스트
- usage 17건 통과(PostgreSQL 16 실DB 테스트 포함, `GC_SCHEMA_TEST_DSN`), fastapi 없으면 라우트 테스트 skip. `make check`, `make test` 통과. origin/claude/gracious-meitner-vp49xe 병합 후 재실행 통과.

## 알아둘 점 (다음 세션)
- 캐시 쓰기: FINAL_TASK 원장은 `cache_creation_input_tokens` 를 ×1.25 로 계산하므로 호출자는 구분 없는 캐시 쓰기를 `cache_write_5m_tokens` 에 넣는다.
- 비용은 `input_tokens` 또는 `output_tokens` 가 NULL 이면 NULL; 캐시 NULL 은 0 으로 취급.
- 가격이 없는 모델은 `LoadResult.rejected=[{index, code:"unknown_model"}]` (내용 없음). 모델 등록은 `pg_store.seed`(시드 2종) 또는 별도 경로 필요.
- compare 의 P10/P50/P90 은 그룹 정답률로 나눈 작업별 값의 분포(맞힌 작업당 기대 비용). 정답 0건 그룹은 제외.
- `wiring.get_service()` 는 첫 호출에 `seed()` 를 실행한다. usage 라우터는 앱 조립(`DOMAINS`)이 자동 마운트.
- `budget_use` 타일은 value=null (quota 도메인 몫).

## baseline 요청
1. openapi `Comparison.groups[]` 에서 `tokens_per_correct`/`cost_list_per_correct` 를 선택으로 바꾸거나 정답 0건 그룹의 표현을 정해 달라(지금은 그룹 제외).
2. identity.api.current_user 가 생기면 `usage/_identity.py` 의 대체 경로 삭제(workspace 와 동일).
3. 모델 카탈로그: 시드는 Haiku 4.5 · Sonnet 5.5 만. Opus 등 가격은 fixture 에 없어 넣지 않았다.
