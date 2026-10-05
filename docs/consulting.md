# 컨설팅 모델 (견적 · 절약 진단 · 개인화 · What-if)

사양 4 절을 계산 규칙으로 옮긴다. 모든 결과는 정수(토큰, micro-USD, ‰)이고 출처를 단다. 견적 · 절감 추정 = ESTIMATED, What-if = SIMULATED. 어떤 결과도 자동으로 적용되지 않는다: 적용은 Proposal(advisor 도메인) → 정책 → `quota.check` → 사용자 확인 → 실행 → 감사.

가격 기호: `p_in(m)`, `p_out(m)`, `p_cr(m)` (캐시 읽기), `p_cw5(m)`, `p_cw1(m)` — `model_prices` 의 Mtok 당 micro-USD. 호출 비용 `cost_i` = `cost_list_nanousd`(정가 환산). 호출의 유효 단가 `eff_i = cost_i / ctx_i` (ctx = `context_tokens`). 정수 나눗셈은 마지막에 한 번 내림한다.

## 1. 실행 전 견적 (estimation)

### 1.1 입력과 특징

| 입력 (EstimateRequest) | 특징 | 거리 가중 |
|---|---|---|
| `task_kind` | 범주 | 3 (불일치 1) |
| `model` | 범주 + `models.tier` | 3 (같은 family 다른 tier 0.5) |
| `structure` (A · B · C · single) | 범주 | 2 |
| `context_mode` (bulk · selective · fresh) | 범주 | 4 (FINAL_TASK 에서 25–63 배 차이의 원인) |
| `context_cap_tokens` | log2 | 1 / log2 차이 |
| `repo_size_loc` | log10 | 1 / log10 차이 |
| `language` | 범주 | 0.5 |
| `description` | 길이(log2)만. 본문은 해시 + 길이로만 저장 | 0.5 |

### 1.2 근거 집합과 범위

1. 후보: 같은 워크스페이스 · 사용자의 `outcome != 'unknown'` 작업 + 전역 사전(FINAL_TASK 100 run, `estimator_models` scope=global).
2. 거리 `d` = Σ 가중 × 불일치, 근거 = d 가 작은 순 상위 `k = 15` (동률은 최신 우선). 가중치 `w = 1/(1+d)`.
3. 각 양(입력 · 캐시 · 출력 토큰, 비용 두 기준, 호출 수, 시간)에 대해 **가중 분위수** P10 / P50 / P90.
4. 성공 확률 = (Σw·correct + 1) / (Σw + 2) (라플라스 평활), ‰ 정수.
5. 사용자 보정: 사용자 근거 수 `n_u`, 혼합 비율 `λ = n_u / (n_u + 10)`. 각 분위수 = λ·사용자 + (1−λ)·전역. `evidence.basis` = `global_prior` · `user` · `blended`.
6. 근거가 3 건 미만이면 범위를 넓힌다: P10 ×0.5, P90 ×2, 그리고 응답에 `evidence.n` 을 그대로 보여 준다(점 하나만 내지 않는다).
7. 추천 구성: 같은 근거에서 `context_mode`, `model`, `structure` 를 바꾼 후보별 맞힌 작업당 비용 P50 이 가장 낮고 성공 확률이 프로필 품질 하한 이상인 구성.

### 1.3 자체 오차

- 견적 id 가 붙은 작업이 끝나면(`usage.task.outcome_set`) `estimate_outcomes` 에 실제값, `ape = |actual − p50| / actual` (‰), `within_p10_p90` 기록.
- 화면 · API: 최근 90 일 MAPE(토큰, 비용), P10–P90 포함률. 목표: 포함률 ≈ 80 %.
- 기준선: `scripts/backtest_estimator.py` 가 FINAL_TASK fixture 에서 **그룹 중앙값 leave-one-out** 기준선의 MAPE 를 출력한다. 새 견적기는 같은 스크립트에서 이 숫자를 이겨야 배포한다(roadmap 의 consulting 작업 done_when).

## 2. 절약 진단 규칙 (advisor)

규칙 = **탐지기(detector) + 절감 추정식(savings) + 제안(proposal)**. 탐지기는 결정적 코드(LLM 아님)이고 `backend/app/domains/advisor/rules/<id>.py` 에 하나씩 둔다. 기본 임계는 `advisor_rules.params` 로 워크스페이스마다 바꿀 수 있다. 각 규칙은 fixture(입력 호출 · 작업 + 기대 결과)를 가지며, 규칙 구현의 단위 시험은 fixture 의 `expect` 를 정확히 재현해야 한다(`scripts/check_docs.py` 가 fixture 존재와 형식을 검사한다).

fixture 형식 (`fixtures/advisor/<id>.json`):

```json
{"rule": "R1", "params": {...}, "prices": {"<model>": {"in": 1000000, "out": 5000000, "cr": 100000, "cw5": 1250000, "cw1": 2000000}},
 "calls": [{"id": 1, "session": "s1", "task": "t1", "model": "...", "role": null, "input": 0, "cache_read": 0, "cache_write": 0,
            "output": 0, "context": 0, "cost_list_nanousd": 0, "cost_cli_microusd": null, "prefix_hash": null, "content_hashes": []}],
 "tasks": [{"id": "t1", "kind": "feature", "model": "...", "outcome": "correct", "first_try_success": true}],
 "expect": {"fires": true, "evidence_call_ids": [1], "savings_p50_microusd": 0, "savings_p10_microusd": 0, "savings_p90_microusd": 0}}
```

규칙 목록 (사양 4.2 표의 7 종):

### R1 bulk_injection — 대량 주입

- detector: `advisor.rules.r1_bulk_injection.detect` — `context_tokens > T` 인 호출 (기본 `T = 50000`).
- savings: p50 = Σ cost_i × (ctx_i − C) / ctx_i (문맥 상한 `C = 20000`); p10 = p50 / 2; p90 = Σ cost_i × 24 / 25 (FINAL_TASK 측정 하한 25 배).
- proposal: `context_cap` — 문맥 상한 `C` 와 선택 주입(ctxpack) 설정 내보내기.
- fixture: `fixtures/advisor/R1.json`

### R2 reread — 다시 읽기

- detector: `advisor.rules.r2_reread.detect` — 한 세션 안에서 같은 `content_hashes` 항목(`<hash12>:<tokens>`)이 2 회 이상 나온 호출. 보조 신호: 세션 문맥이 단조 증가하고 마지막/처음 ≥ 3 (호출 ≥ 20) 이면 `rlo.ctxbudget.simulate(contexts, soft, hard, reset_to)` 의 `saved_pct` 를 쓴다(새 계산기를 만들지 않는다).
- savings: p50 = Σ (두 번째 이후 등장마다) tokens_block × eff_i; p10 = p50 / 2; p90 = p50 + 세션 비용 × saved_pct (보조 신호가 있을 때, 없으면 p90 = p50).
- proposal: `config_export` — fresh 모드, State 재사용(ga `STATE.md`) 템플릿.
- fixture: `fixtures/advisor/R2.json`

### R3 cache_miss — 캐시 미스

- detector: `advisor.rules.r3_cache_miss.detect` — 같은 `prompt_prefix_hash` 를 가진 호출이 5 분 창 안에 2 건 이상, 그중 `cache_read_tokens = 0` 이고 `input_tokens ≥ models.min_cache_tokens` 인 호출(첫 호출 제외). NULL 은 0 으로 보지 않는다(건너뜀).
- savings: 고정 앞부분 비율 s 로, 첫 호출 이후 각 호출 i 에 대해 s × input_i × (p_in − p_cr), 빼기 첫 호출의 쓰기 할증 s × input_first × (p_cw5 − p_in). p10: s = 0.25, p50: s = 0.5, p90: s = 0.9. 음수면 0.
- proposal: `template` — 프롬프트 앞부분 고정, 모델별 최소 캐시 길이 안내.
- fixture: `fixtures/advisor/R3.json`

### R4 model_overkill — 모델 과잉

- detector: `advisor.rules.r4_model_overkill.detect` — (작업 종류, 모델) 묶음에서 작업 ≥ 5, 첫 시도 성공률 ≥ 90 %, 같은 family 에 더 낮은 tier 모델이 있음.
- savings: r = p_in(lower) / p_in(current), q = 하위 모델 성공률(개인 통계, 없으면 전역 사전, 그것도 없으면 0.9). p50 = Σ cost_i × (1 − r / q); p10 은 q − 0.1, p90 은 q = 1. 음수면 0.
- proposal: `router_tier` — 라우터 단계 하나 낮추기(ga router `tier` 설정 내보내기).
- fixture: `fixtures/advisor/R4.json`

### R5 model_underkill — 모델 과소

- detector: `advisor.rules.r5_model_underkill.detect` — (작업 종류, 모델) 묶음에서 작업 ≥ 3, 실패율 f = incorrect / (correct + incorrect) ≥ 30 %, 더 높은 tier 가 있음.
- savings: C = 묶음의 작업당 평균 비용, R = p_in(upper) / p_in(current), q_up = 상위 성공률(없으면 0.95). 맞힌 작업당 비용 현재 C / (1 − f), 상위 C × R / q_up. p50 = correct × (C / (1 − f) − C × R / q_up); p10 은 q_up − 0.1, p90 은 q_up = 1. 음수면 발화하지 않는다.
- proposal: `router_tier` — 한 단계 올리기.
- fixture: `fixtures/advisor/R5.json`

### R6 runner_overhead — 실행기 오버헤드

- detector: `advisor.rules.r6_runner_overhead.detect` — CLI 비용과 정가 환산이 둘 다 있는 호출 ≥ 10, Σcli / Σlist ≥ 1.3 (FINAL_TASK 평균 1.91).
- savings: 작은 호출(ctx < 5000) 집합 S 에서 overhead = Σ_S (cli_i − list_i). p50 = overhead / 2 (호출 2 개씩 묶기), p10 = overhead / 4, p90 = overhead × 9 / 10 (bare 호출).
- proposal: `config_export` — bare 호출, 호출 묶기 설정.
- fixture: `fixtures/advisor/R6.json`

### R7 judge_waste — 판정 낭비

- detector: `advisor.rules.r7_judge_waste.detect` — `role` 이 판정 역할(기본 `judge`, `hub_judge`)인 호출, 그 작업의 종류가 기계적 검사 가능(`feature`, `bug`, `refactor`).
- savings: p50 = Σ cost_i (판정 호출 정가 환산 전부; `ga judge` 는 LLM 호출 0), p10 = p50 / 2, p90 = p50.
- proposal: `template` — 시험 · 변이 · 계약 검사를 `ga judge` 로 옮기는 설정.
- fixture: `fixtures/advisor/R7.json`

규칙 실행: `usage.calls.ingested` 이벤트마다 해당 기간(기본 최근 30 일)에 대해 다시 돌린다. 같은 (규칙, 기간)의 finding 은 갱신한다. 절감 추정은 기준 `list` 로 낸다(`cli` 기준은 커버리지가 있을 때 detail 에 함께).

## 3. 개인화 (profile)

- 프로필: data-model.md 6 절의 `profiles`. `store_bodies` 기본 false.
- 개인 통계(`personal_stats`): 키 (user, workspace, task_kind, model, structure, context_mode). 값: 작업 수, 정답 수, 첫 시도 성공 수, 맞힌 작업당 토큰 · 비용(두 기준). 이것이 사양의 "사용자별 라우터 통계"다: ga router 의 `learn` 키 `class|backend|model|tier` → `{runs, accepted, tokens, tokens_per_accepted}` 와 같은 모양이어서 (나중) 플랫폼 안 ga 실행 때 라우터 초기 상태로 내보낼 수 있다(`router.json`, schema `ga-node-router/1`).
- 견적기 보정: 1.2 절 5 단계의 λ.
- 맞춤 추천: 같은 task_kind 에서 맞힌 작업당 비용이 현재 구성보다 낮고, 정답률 ≥ 프로필 품질 하한, 근거 ≥ 5 인 구성을 찾는다. 문장: "당신의 `<kind>` 작업은 `<config>` 구성이 맞힌 작업당 `<Y>`% 싸다 (근거 N 건)". 적용하려면 Proposal 로 넘긴다.

## 4. What-if (simulation)

입력 = 가정 목록(비어 있으면 422) + 데이터 기준(기간, 프로젝트). 결과 = 기준선(MEASURED/CALCULATED 지표) + 시뮬레이션 범위(SIMULATED). 저장되는 `basis` 에 호출 수 · 작업 수 · 가격표 버전 · 개인 통계 버전이 들어간다.

| 가정 kind | 재계산 |
|---|---|
| `model_swap` {from, to} | 같은 토큰에 새 가격(P50). 토큰 비율 = 개인 통계 tokens_per_correct(to)/(from) (없으면 전역, 없으면 1). 정답률 변화 = 두 모델 성공률 차, 범위는 근거 수에 따른 베타 분포 P10/P90 |
| `context_cap` {tokens} | 호출별 ctx' = min(ctx, cap); 세션 단위는 `rlo.ctxbudget.simulate` 재사용. 정답률 범위는 FINAL_TASK bulk vs selective(차이 없음 ~ −1/5) |
| `node_count` {n} | 구조별 개인 통계(A/B/C)의 호출 수 · 토큰을 노드 수 비례로 외삽, 범위는 근거 분위수 |
| `cache_prefix_fixed` {} | R3 의 절감식 적용 |
| `structure` {to} | 구조별 맞힌 작업당 비용 비율(개인 → 전역 FINAL_TASK) |

화면은 결과 옆에 가정 목록과 기준을 항상 같이 보여 준다(visualization.md 의 SIMULATED 표기).
