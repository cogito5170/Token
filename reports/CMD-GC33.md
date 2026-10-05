```ga
{"schema":"report/2","from":"consulting","handled":[{"id":"CMD-GC33","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc33","sha":"f2be1ad3d5ca1d869b0ec22f5690f05765f80953"}],"tests":{"passed":23,"failed":0,"skipped":1},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["empty/missing/bad assumptions -> SimulationError 422, nothing saved: test_simulation.ValidationTest; route 422 test skips without fastapi"]},{"id":"D2","state":"met","evidence":["every kind returns provenance SIMULATED, ranges SIMULATED, basis has price_version: ProvenanceTest"]},{"id":"D3","state":"met","evidence":["model_swap on identical prices -> delta 0: ModelSwapTest.test_identical_prices_change_cost_by_zero"]}]}
```

# CMD-GC33 — Simulation (what-if)

## 한 일
- `backend/app/domains/simulation/`: `service.py`(검증, 5 종 가정, 합성, to_proposal), `store.py`(Memory/Pg `simulations`), `wiring.py`, `api.py`(simulate/get/to_proposal), `router.py`(POST/GET /simulations), `tests/`.
- 방식: 기준선 = 기간 내 호출의 `cost_list_microusd` 합. 가정을 순서대로 작업 복사본에 적용, 각 가정이 (low, mid, high) nano-USD 차이를 내고 합산 → 기준선 + 차이(정렬). 토큰×가격으로 다시 계산한 값의 **차이만** 더하므로 같은 가격 model_swap 은 정확히 0.
- model_swap: 개인 통계 tokens_per_correct 비율(종류별 → 풀링, 없으면 1), 정답률 변화는 Beta(Laplace) 정규근사 P10/P90. context_cap: 호출별 상한 + `rlo.ctxbudget.simulate`(주입, 없으면 기록 후 호출별만). node_count: 선형, 범위는 작업 비용 분위수(근거 3 미만이면 ×0.5/×2). cache_prefix_fixed: R3 비율 25/50/90 %. structure: 개인 통계 cost_list_per_correct 비율.
- 모든 결과에 assumptions, basis{from,to,calls,tasks,price_version,stats_version}, assumptions_applied(근거 · 가정 상수) 저장. 이벤트 `simulation.simulation.completed`.

## 시험
simulation 24 (1 skip: fastapi 없음), make check 0 problems, make test OK. 변이(swap 가격 무시)로 3 실패 확인.

## 열린 문제 / baseline 요청
1. advisor.api.submit_proposal(ws, origin, origin_ref, kind, change, expected_savings, actor) 에 맞춰 연결 완료(GC30 병합 후 시그니처 확인). wiring 은 import 로 찾는다.
2. **usage.api.prices()** 필요: {model:{version,in,out,cr,cw5}} (micro-USD/Mtok). 지금은 없어 `_prices` 가 {} → simulate 503. 또 usage.api.calls 에 `prompt_prefix_hash` 가 없어 cache_prefix_fixed 는 "같은 세션 300 초 이내" 로 근사. cache_write 1h 구분도 없어 5m 가격 적용.
3. `app/main.py` 에 simulation router 등록(core-backend).
4. `rlo.ctxbudget.simulate` 는 이 환경에 없어 실제 반환 형태 미확인: `saved_pct`(퍼센트, dict 또는 속성) 가정, 인자 soft=hard=cap, reset_to=cap/2 는 추정. 설치 후 확인 필요.
5. 상수(문맥 상한 정답률 −200/−100/0‰, p90 = p50 절감의 절반, 800/1250‰ 폭)는 임의 기본값이며 assumptions_applied 로 노출. PG 저장소는 DSN 시험 없이 작성(스키마 컬럼 그대로).
