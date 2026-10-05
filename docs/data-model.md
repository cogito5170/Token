# 데이터 모델

DDL 원본은 `docs/schema.sql` (PostgreSQL 16, 빈 DB 에 그대로 적용된다). 이 문서는 그 의미와 수집 · 쿼터 규칙을 적는다. 테이블 소유는 `docs/domain-model.md`.

## 1. 공통 규칙

- 기본 키: `uuid` (`gen_random_uuid()`), 시계열 `usage_calls` 만 `bigint identity` (삽입 순서 · 인덱스 크기).
- 시간: `timestamptz`, UTC 저장. 화면 표시는 사용자 시간대.
- **정수만:** 토큰은 `bigint`, 금액은 `bigint` micro-USD(`*_microusd`, 1 USD = 1 000 000). 실수 금액은 API 경계에서도 쓰지 않는다(JSON 정수). 가격표는 Mtok 당 micro-USD 정수(`$1/Mtok` = `1000000`), 1 토큰 비용 = `tokens * price_per_mtok / 1e6` 를 정수 나눗셈으로 계산하고 **호출 단위로 반올림하지 않고** 집계 단위에서 한 번만 반올림하기 위해 `cost_list_nanousd`(1e-9) 를 호출 행에 둔다. (FINAL_TASK 의 싼 호출은 $0.0005 수준이다.)
- 출처: 숫자 열 묶음마다 `provenance` (`MEASURED | CALCULATED | ESTIMATED | SIMULATED`) 를 둔다. 같은 행 안에서도 비용 두 기준은 출처가 다르므로 열 이름으로 고정한다(`cost_list_*` = CALCULATED, `cost_cli_*` = MEASURED, `cost_provider_*` = MEASURED).
- 모르는 값은 NULL. 0 으로 채우지 않는다(l0-telemetry 의 `reported_null` 규칙을 따른다).
- 모든 사용자 데이터 행은 `workspace_id` 를 가진다. 범위 검사는 workspace 도메인의 `require_member` 가 한다.

## 2. 정규화 사용 모델

```
Source ─< Upload ─< IngestJob ─< UsageCall >─ UsageSession
                                    │  └──── UsageTask (작업: 정답 여부 · 종류 · 구조)
                                    └── Model ─< ModelPrice (유효 기간)
```

### 2.1 UsageCall (`usage_calls`) — LLM 호출 1 건

| 열 | 형 | 출처 | 설명 |
|---|---|---|---|
| `id` | bigint | — | |
| `workspace_id`, `project_id` | uuid | — | 범위 |
| `source_id`, `ingest_job_id` | uuid | — | 어디서 왔는가 |
| `session_id` | uuid null | — | `usage_sessions` |
| `task_id` | uuid null | — | `usage_tasks` |
| `source_kind` | text | — | `claude_code` · `ga_l0` · `anthropic_export` · `openai_export` · `otel` |
| `provider` | text | MEASURED | `anthropic` · `openai` · `gemini` |
| `model_id` | text | MEASURED | 공급자 모델 문자열 그대로(`claude-haiku-4-5-20251001`), `models.id` 참조 |
| `occurred_at` | timestamptz | MEASURED | 호출 시각. 원천에 없으면 업로드 시각 + `time_basis='ingested'` |
| `time_basis` | text | — | `reported` · `ingested` |
| `call_index` | int null | MEASURED | 세션 안 순서 |
| `role` | text null | MEASURED | ga 역할(`hub`, `worker`, `hub_judge`, …) 또는 null |
| `input_tokens` | bigint null | MEASURED | 캐시에서 오지 않은 입력 (l0 `input_tokens`) |
| `cache_read_tokens` | bigint null | MEASURED | l0 `cache_read_input_tokens` |
| `cache_write_5m_tokens` | bigint null | MEASURED | l0 `cache_creation_5m_input_tokens` (구분 없으면 `cache_creation_input_tokens` 를 여기에) |
| `cache_write_1h_tokens` | bigint null | MEASURED | l0 `cache_creation_1h_input_tokens` |
| `output_tokens` | bigint null | MEASURED | 생각 토큰 포함 |
| `thinking_tokens` | bigint null | MEASURED | 별도 보고가 있을 때 |
| `context_tokens` | bigint null | CALCULATED | input + cache_read + cache_write (rlo `normalize()["context"]`) |
| `tool_calls` | int null | MEASURED | |
| `latency_ms` | int null | MEASURED | |
| `cost_list_nanousd` | bigint null | CALCULATED | 정가 환산(가격표 `model_prices` 버전 `price_version`) |
| `price_version` | int null | — | 계산에 쓴 가격표 버전 |
| `cost_cli_microusd` | bigint null | MEASURED | CLI 보고 비용(`total_cost_usd`, cost-state) |
| `cost_provider_microusd` | bigint null | MEASURED | 공급자 내보내기의 금액 열 |
| `prompt_prefix_hash` | text null | CALCULATED | 앞부분(최대 4 KiB) HMAC-SHA256 12 hex. 캐시 미스 · 다시 읽기 탐지용. 본문은 저장 안 함 |
| `content_hashes` | text[] null | CALCULATED | 주입된 파일 · 블록별 `<hash12>:<tokens>` (다시 읽기 탐지, R2), 해시는 l0 `Hasher` |
| `dedupe_key` | text | — | `sha256(source_kind, response_id 또는 (session, call_index, occurred_at, tokens))`, 워크스페이스 안에서 unique |
| `body_ref` | text null | — | 사용자가 본문 보관을 켠 경우에만 객체 저장소 경로 |

### 2.2 UsageSession (`usage_sessions`)

원천의 세션 1 개(Claude Code transcript 파일 1 개, ga 노드 1 개, 내보내기의 하루 · 키 조합 1 개). `client`(`claude_code` · `codex` · `gemini_cli` · `api` · `ga`), `external_id`, `started_at`, `ended_at`, 합계 캐시 열(`calls`, 토큰 4 종, 비용 두 기준) — 합계는 CALCULATED 이며 `usage` 가 적재 때 갱신한다.

### 2.3 UsageTask (`usage_tasks`)

"맞힌 작업당 비용"의 분모. 작업 1 개 = 사용자가 의도한 일 1 개(ga 의 work item, FINAL_TASK 의 run, 사용자가 표시한 세션 묶음).

- 특징: `kind` (`feature` · `bug` · `refactor` · `docs` · `other`), `structure` (ga 구조 `A` · `B` · `C` 또는 `single`), `context_mode` (`bulk` · `selective` · `fresh`), `context_cap_tokens`, `repo_size_loc`, `language`, `model_primary`, `node_count`.
- 결과: `outcome` (`correct` · `incorrect` · `unknown`), `outcome_source` (`judge` · `user` · `fixture`), `first_try_success` bool.
- 합계(CALCULATED): `calls`, 토큰 4 종, `cost_list_nanousd`, `cost_cli_microusd`, `duration_ms`, `max_call_input`.

### 2.4 Model 과 가격표

- `models`: `id`(공급자 모델 문자열), `provider`, `family`(`claude` · `gpt` · `gemini`, ga router 의 FAMILIES 와 같다), `tier`(정수, 높을수록 상위), `min_cache_tokens`.
- `model_prices`: `(model_id, version, effective_from)` 마다 Mtok 당 micro-USD 정수 5 종: `input`, `output`, `cache_read`, `cache_write_5m`, `cache_write_1h`. 기본 배율은 FINAL_TASK 와 같다(캐시 쓰기 ×1.25, 1h ×2, 캐시 읽기 ×0.1). 가격표는 데이터이고 코드 상수가 아니다. 가격이 바뀌면 새 버전 행을 넣고 재계산 작업이 `cost_list_nanousd` 와 `price_version` 을 갱신한다.

### 2.5 집계 (`usage_daily`)

`(workspace_id, project_id, day, model_id, source_kind)` 일별 합계. 차트 API 는 기간이 하루 이상이면 이 표를, 하루 미만이면 `usage_calls` 를 읽는다. `usage` 가 적재 트랜잭션 안에서 갱신한다(멱등: 해당 일 · 키를 다시 합산).

## 3. 출처별 매핑

| 원천 | 파서 (재사용) | → UsageCall | 비고 |
|---|---|---|---|
| Claude Code `.jsonl` | `telemetry.collect.from_cc_jsonl(path, run_id, hasher)` | `llm.response` 1 건 = 호출 1 건. 토큰 열은 이벤트 data 의 l0 USAGE 필드 그대로. `model`, `call_index`, `response_id`, `t_start_ms`. `run.snapshot.cost_usd` 의 증가분을 직전 호출들의 `cost_cli_microusd` 로 분배하지 않고 세션 합계(`usage_sessions.cost_cli_microusd`)로 둔다 | 사이드체인은 파서가 이미 건너뛴다. 시각(`at`)이 비면 `time_basis='ingested'` |
| ga L0 `.jsonl` (`.ga/telemetry/*.jsonl`, `.ga/nodes/*/telemetry.jsonl`) | `telemetry.ledger.read_lenient(path)` | `run.end` 1 건 = 턴 1 건을 호출 1 건으로(`reported_*_tokens`, `cost_usd` → `cost_cli_microusd`, `api_calls`, `num_turns`). `llm.response` 가 있으면 그것을 우선. `peer.message.*` 는 (나중) `run_messages` | 잘못된 줄은 `ingest_rejects` |
| Anthropic usage 내보내기 CSV/JSON | 열 매핑 어댑터 → `telemetry.usage.l0_usage("anthropic", u)` | 행 1 개(시간 버킷 × 모델 × 키)를 "합계 호출" 1 건으로(`call_index` null, `role='aggregate'`). 금액 열 → `cost_provider_microusd` | 내보내기 파서가 l0-telemetry 에 없다 → baseline 요청. 그 전까지 어댑터는 열 이름 → usage dict 매핑 표만 가진다(파싱 로직은 stdlib `csv`) |
| OpenAI usage 내보내기 CSV/JSON | 같은 방식 → `l0_usage("openai", u)` | 같음. 입력 = prompt − cached 는 l0_usage 가 한다 | 같음 |
| FINAL_TASK `runs.jsonl` (fixture) | 플랫폼 코드가 아님. `scripts/backtest_estimator.py` 와 estimation 사전(prior) 적재기만 읽는다 | run 1 건 = 작업 1 건, `calls[]` = 호출 | `void: true` 행 제외 |

## 4. 수집 파이프라인

```
POST /uploads ──► source.create_upload ──► uploads(row, sha256) ──event──► ingestion.enqueue
                                                                      │
worker loop: claim_next()  (SELECT … FOR UPDATE SKIP LOCKED on ingest_jobs where state='queued')
  1. detect     형식 감지(확장자 + 첫 줄 모양) → source_kind
  2. parse      위 표의 파서. 줄 단위 오류는 ingest_rejects(line_no, error_code) 로, 원문 줄은 저장하지 않는다
  3. scrub      비밀값 제거(아래) — 파서 출력의 문자열 필드에 적용. 본문은 기본적으로 버린다
  4. normalize  UsageCall 생성, context_tokens 계산, dedupe_key
  5. load       usage.load_calls (한 트랜잭션: calls + sessions/tasks 합계 + usage_daily + price)
  6. analyze    usage.calls.ingested 발행 → quota, advisor, profile, estimation 구독자가 재계산
  7. done       ingest_jobs.state='done', counts; 실패 시 'failed' + error_code (메시지에 원문 없음)
각 단계 전환마다 ingest_job_events(seq, stage, pct, counts) 1 행 → SSE /ingest-jobs/{job}/events
```

- **멱등:** 같은 파일(sha256)을 다시 올리면 같은 dedupe_key 로 `ON CONFLICT DO NOTHING`. 결과 수(`inserted`, `duplicates`, `rejected`)를 작업에 남긴다.
- **크기 한도:** 파일 200 MiB, 줄 4 MiB (설정 `GC_UPLOAD_MAX_BYTES`). 넘으면 거부.
- **재시도:** 작업은 3 회까지 다시 claim. `attempts`, `last_error_code`.

### 4.1 비밀값 제거 (scrub)

- 기본: 프롬프트 · 코드 · 도구 출력 본문은 **저장하지 않는다**. 남는 것은 토큰 수, 모델, 시각, 역할, 해시(`prompt_prefix_hash`, `content_hashes`)뿐이다. 도구 대상(경로 · URL · 쿼리)은 l0-telemetry `Hasher` 로 이미 해시된다.
- 본문 보관을 사용자가 켜면(`profiles.store_bodies=true`) 저장 전에 패턴 제거를 한다: `sk-ant-…`, `sk-…`(OpenAI), `AIza…`(Google), `ghp_` / `github_pat_`, `AKIA…`(AWS), `xox[abpr]-`(Slack), `-----BEGIN … PRIVATE KEY-----`, JWT 모양(`eyJ…\.eyJ…\.`), `password=` / `token=` / `secret=` 대입문, 32 자 이상 고엔트로피 문자열. 치환 값은 `[REDACTED:<kind>]`.
- 범용 비밀값 제거기는 의존성들에 없다 → baseline 요청(l0-telemetry 에 두기를 제안). MVP 는 `backend/app/domains/ingestion/scrub.py` 의 패턴 표로 시작하고 fixture 로 시험한다.
- 해시 키는 환경 변수 `TELEMETRY_HASH_KEY` (워크스페이스별 파생 키: HKDF(master, workspace_id)). 키가 바뀌면 해시 비교 연속성이 끊긴다는 점을 문서화한다.

## 5. 쿼터 모델 (두 기준)

- 기준 `list`: Σ `cost_list_nanousd` / 1000 → micro-USD (CALCULATED).
- 기준 `cli`: Σ `cost_cli_microusd` (MEASURED). 값이 없는 호출 비율 `cli_coverage` 를 함께 돌려준다(커버리지 < 100 % 이면 화면에 "부분" 표시).
- `budgets`: `scope` (`workspace` · `project` · `task`), `period` (`day` · `month` · `task`), `measure` (`list` · `cli`), `limit_microusd`, `thresholds` (기본 `{50,80,100}`), `action_at_limit` (`alert` · (나중) `stop`).
- 소진 예측: 기간 시작부터 일별 누적 → 최근 7 일 기울기의 선형 외삽, 구간은 일별 사용의 P10/P90 기울기. 결과 `projected_exhaust_at` (ESTIMATED) 과 구간.
- 경보: 임계를 처음 넘을 때 `budget_alerts` 1 행(같은 임계 · 기간 중복 없음) → `quota.alert.raised` → notification.
- 두 기준의 비율 `cli / list` (FINAL_TASK 평균 1.91, 싼 호출일수록 높다)은 advisor R6 의 입력이다.

## 6. 견적 · 개인화 · What-if 데이터

| 모델 | 테이블 | 핵심 열 |
|---|---|---|
| 견적 | `estimates` | `request` jsonb(작업 설명은 해시 + 길이만, 특징), `features` jsonb, 결과 열 `tokens_p10/p50/p90` (입력 · 캐시 · 출력 각각), `cost_list_p*`, `cost_cli_p*`, `calls_p*`, `duration_ms_p*`, `success_prob` (‰ 정수), `evidence_n`, `estimator_version`, `provenance='ESTIMATED'` |
| 근거 | `estimate_evidence` | `(estimate_id, task_id, weight_permille, distance_permille)` |
| 오차 | `estimate_outcomes` | `estimate_id`, `task_id`, 실제 토큰 · 비용, `ape_permille` (절대 백분율 오차 ‰) |
| 견적기 | `estimator_models` | `scope` (`global` · `workspace` · `user`), `version`, `params` jsonb, `fitted_on_n`, `mape_permille` |
| 개인 통계 | `personal_stats` | `(user_id, workspace_id, task_kind, model_id, structure, context_mode)` → `tasks`, `correct`, `first_try_success`, `tokens_per_correct`, `cost_list_per_correct_nanousd`, `cost_cli_per_correct_microusd`, `updated_at` |
| What-if | `simulations` | `assumptions` jsonb (필수, 비어 있으면 거부), `basis` jsonb (기간, 호출 수, 가격표 버전, 개인 통계 버전), 결과 범위 jsonb, `provenance='SIMULATED'` |

자세한 수식은 consulting.md.
