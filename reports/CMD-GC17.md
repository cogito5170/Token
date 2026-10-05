```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC17","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc17","sha":"SHA40"}],"tests":{"passed":13,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["tests/test_quota.py::test_used_returns_both_measures_and_cli_coverage","tests/test_quota.py::test_alert_80_once_per_period","tests/test_quota.py::test_check_blocks_over_limit"]}]}
```

## 한 일
quota 도메인 구현: 예산(list · cli 두 기준, 일 · 월 · 작업 기간, workspace · project · task 범위), 두 기준 사용량 `used.list` / `used.cli`(cli 는 호출에 cli 비용이 없으면 `value` null, `coverage_permille` < 1000 은 usage.api.summary 값을 그대로 전달), 소진 예측(`burn`: 누적 + 일일 증가량의 P10/P50/P90 로 외삽, `exhaust_at_p10/p50/p90`), 임계 경보(`evaluate`: 예산 · 기간 · 임계당 한 번, 저장소 UNIQUE 키 + 메모리 저장소 동일 규칙), `quota.api.check(ws, scope, extra_cost, project_id, cost_cli)` 제안 게이트, 라우트(`/budgets*`, `/quota/alerts`; 조회 member, 쓰기 admin, `budget.create`/`budget.archive` 감사).

## 파일
`backend/app/domains/quota/{service,api,wiring,pg_store,router}.py`, `tests/test_quota.py`, `tests/__init__.py`.

## 테스트
quota unittest 13개 통과, `make check` · `make test` 통과(PG 스키마 테스트는 DSN 없어 skip). origin/claude/gracious-meitner-vp49xe 병합 후 재실행 통과.

## 열린 문제
- `check()` 는 `action_at_limit` 과 무관하게 한도 초과를 차단하고 `action_at_limit` 을 결과에 싣는다(게이트 해석은 advisor 가 결정).
- `period=task` 예산은 최근 30일 사용량을 기준으로 한다(작업 단위 사용량 API 가 없음).
- `pg_store.py` 는 DB 로 실행 검증하지 않았다(DSN 없음).
- 알림(notification) 연동은 `notify` 콜백 주입점만 있다. `evaluate` 를 호출할 시점(적재 후 · 주기)은 worker/baseline 결정 필요.

## baseline 요청
- usage.api.summary 는 `budget_use` 타일을 null 로 둔다. quota 값 채우기는 별도 항목 필요.
- 다음 세션: `quota.api.check` / `burn` / `evaluate` 가 공개 면이다.
