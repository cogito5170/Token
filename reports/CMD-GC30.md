```ga
{"schema":"report/2","from":"consulting","handled":[{"id":"CMD-GC30","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc30","sha":"cb5bd8d7ffb01d0b9df42d921a10ba29ce7ffa2c"}],"tests":{"passed":25,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/app/domains/advisor/tests/test_rules.py::test_every_fixture_reproduced_exactly (R1-R7 evidence ids, p10/p50/p90 exact)"]},{"id":"D2","state":"met","evidence":["test_service.py::test_apply_without_confirm_is_refused"]},{"id":"D3","state":"met","evidence":["test_service.py::test_over_budget_apply_is_blocked"]},{"id":"D4","state":"met","evidence":["test_service.py::test_apply_with_confirm_applies_and_audits, test_reject_is_final_and_audited, test_policy_blocks_before_budget_is_asked"]}]}
```

## 한 일

- `rules/r1..r7`: 결정적 탐지기. 정확한 Fraction, nano-USD, 마지막에 한 번만 내림(`Finding.of`). fixture R1-R7 의 기대값(증거 호출 id, p10/p50/p90 micro-USD)을 정확히 재현.
- `service.py`: `run_rules`(같은 (규칙, 기간) finding 갱신), `list_rules`/`list_findings`, `submit_proposal`(모든 출처의 단일 입구), `decide`(accept/reject/apply). apply 게이트 순서: 상태(accepted) → 정책(역할, repo_change·budget_change 는 admin) → `quota.check` → `confirm is True` → 적용. 정책·예산 거부는 state=blocked + blocked_reason, confirm 누락은 409 로 거부하고 제안은 accepted 로 남는다. 모든 단계가 `proposal_decisions` 와 `audit.record`(proposal.create|accept|reject|apply|blocked)에 남는다. 30 일 지나면 expired.
- `pg_store.py`, `wiring.py`(usage.calls.ingested 구독), `api.py`, `router.py`(/advisor/rules, /advisor/findings, /proposals, /proposals/{id}, /proposals/{id}/decision).

## 변경 파일
backend/app/domains/advisor/{api,pg_store,router,service,wiring}.py, rules/*.py, tests/test_rules.py, tests/test_service.py.

## 시험
item check argv: 25 passed. make check, make test green (psycopg/fastapi 없음 → PgStore 와 router 는 이 컨테이너에서 실행 못 함; 아래 열린 문제).

## 열린 문제
- PgStore SQL 과 router 는 실행 검증 못 함(psycopg, fastapi 미설치, 로컬 PostgreSQL 서버 없음). schema.sql 열 이름 기준으로 작성. finding 의 proposal 템플릿은 `advisor_findings.detail._proposal` 에 저장(스키마에 칸 없음).
- R2 보조 신호(rlo.ctxbudget.simulate)는 저장소에 없어서 미구현: p90 = p50, detail.ctxbudget_signal=false.
- R4/R5 의 `tiers` 는 규칙 params 로 받는다(기본 빈 값 → 발화 안 함). 워크스페이스가 `advisor_rules.params` 에 넣거나 baseline 이 기본값을 정해야 한다.

## baseline 요청 (다른 도메인 파일이라 내가 바꾸지 않음)
1. usage.api.calls 항목에 `prompt_prefix_hash`, `content_hashes`, `cost_list_nanousd`(또는 마이크로가 아닌 나노), `cache_write_tokens` 분리 없이도 되지만 앞 세 개는 R2/R3/R1-R7 정확도에 필요. 지금 없으면 R2/R3 는 발화하지 않는다(null 을 0 으로 보지 않음). advisor 는 `prompt_prefix_hash`, `content_hashes` 키 이름을 기대한다.
2. usage.api.tasks 항목에 `first_try_success`(R4 필요; 없으면 R4 미발화).
3. usage.api 에 `prices()` -> {model: {in,out,cr,cw5,cw1}} (micro-USD/Mtok). advisor wiring 이 `getattr(usage,"prices")` 로 찾고 없으면 {} (R3-R5 미발화).
4. app 시작 시 `advisor.wiring.subscribe()` 호출(usage.calls.ingested 구독).

## 다음 세션이 알 것
- 탐지기 시그니처: `detect(calls, tasks, prices, params)`, 규칙별 `DEFAULTS`. 시험은 fixture 가격을 전부 합친 표를 쓴다(R4/R5 는 이웃 tier 가격이 필요한데 fixture 한 개에는 없음).
- 다른 도메인(report CMD-GC34)은 `advisor.api.list_findings(ws, from, to)` 로 읽는다(OpenAPI Finding 모양의 dict).
