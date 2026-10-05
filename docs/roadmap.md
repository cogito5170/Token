# 로드맵과 병렬 작업 계획

## 1. 단계

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 아키텍처 · 계약 · 작업 목록 (CMD-GC0, 이 문서) | 완료 |
| 1 | MVP (사양 7 절 "반드시") — 아래 작업 21 개를 ga 0.6 노드 풀(동시 3)로 | 다음 |
| 2 | 나중 목록: 플랫폼 안 ga 실행(Run 도메인 · 노드 타임라인 · 동료 네트워크 · 판정 · 작업 흐름), 공급자 API 자동 연동 + 키 보관(integration), 팀 권한 세분화, Slack, 공개 API, 벤치마크, 주간 리포트 PDF, 결제 | 설계만 |

## 2. 병렬 규칙

1. 역할 5 개: `frontend`, `core-backend`, `ingestion-analytics`, `consulting`, `infra`. 작업 하나 = 역할 하나.
2. 작업의 `files` 는 docs/ownership.md 에서 그 역할의 행 안에 있다. 의존 관계가 없는 두 작업은 같은 파일을 갖지 않는다(`check_docs.py` 검사). 그래서 동시에 돌아도 서로 덮어쓰지 않는다.
3. 공유 계약(openapi.yaml, schema.sql, domain-model.md, visualization.md, consulting.md, fixtures/advisor, migrations, pyproject)은 `"kind": "contract"` 작업만 바꾼다. 다른 작업이 계약 변경이 필요하면 멈추고 contract 작업을 제안한다(ga 의 `work` 블록 = Proposal).
4. 작업 간 연결은 **인터페이스**(`app/domains/<d>/api.py` 함수, openapi 경로)로만. 의존 작업이 아직 없으면 인터페이스 서명에 맞춘 가짜(fake)로 시험한다.
5. `done_when` 은 실행 가능한 명령(argv) 하나다. `ga judge` 가 그것과 변이 · 소유표 검사를 돌린다.
6. 내보내기: `python3 scripts/export_work.py` → work/1 JSON 줄(한 줄에 하나) → `ga work add -`.

## 3. 의존 그래프 (요약)

```
GC10 contract ─┬─ GC11 infra
               └─ GC12 core ─┬─ GC13 identity ─ GC14 workspace ─┬─ GC15 audit ─ GC16 notification
                             │                                  ├─ GC20 source ─┐
                             │                                  └─ GC21 usage ──┴─ GC22 ingestion ─ GC23 adapters
                             │                                        ├─ GC17 quota
                             │                                        ├─ GC30 advisor (← GC15, GC17)
                             │                                        ├─ GC31 estimation ─ GC33 simulation
                             │                                        ├─ GC32 profile
                             │                                        └─ GC34 report (← GC30, GC17)
GC40 frontend shell (← GC10) ─┬─ GC41 usage screens   (계약 + fake API 로 시작, 실제 API 는 GC21)
                              ├─ GC42 consulting screens
                              └─ GC43 ingest/notify/audit screens
```

첫 물결(동시 3): GC10 → 그 다음 GC11 · GC12 · GC40. 이후 core → ingestion-analytics → consulting 순서로 열리고 frontend 는 fake API 로 나란히 간다.

## 4. 작업 항목

아래 블록이 원본이다(JSON). 필드: `id`, `role`, `kind` (`feature` | `contract`), `goal`, `files` (소유 경로 패턴), `depends_on` (작업 id), `interfaces` (의존하는 인터페이스), `done_when` (argv 하나), `done_when_text`.

```work-items
[
 {"id": "CMD-GC10", "role": "core-backend", "kind": "contract",
  "goal": "Contract v0.1 materialized: backend/migrations/0001_init.sql identical to docs/schema.sql, a test that applies all migrations to an empty PostgreSQL, and a contract test that no OpenAPI response schema has a secret-bearing field. Template for every later contract change.",
  "files": ["backend/migrations/**", "tests/contract/**"],
  "depends_on": [],
  "interfaces": ["docs/schema.sql", "docs/api/openapi.yaml"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "tests/contract", "-t", "."],
  "done_when_text": "migration file equals schema.sql; applies to an empty DB (skips only if no PostgreSQL); no secret fields in response schemas; check_docs.py and validate_openapi.py still exit 0"},

 {"id": "CMD-GC11", "role": "infra", "kind": "feature",
  "goal": "Dev environment and CI: docker-compose (postgres:16, api, worker, web), Makefile targets (db-up, migrate, test, check), .env.example with names only, CI workflow running make check + make test + schema apply, and a secret-pattern grep over the tree.",
  "files": ["infra/**", ".github/**", "Makefile", ".env.example", ".gitignore", "README.md"],
  "depends_on": ["CMD-GC10"],
  "interfaces": ["scripts/check_docs.py", "scripts/validate_openapi.py", "backend/migrations/**"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "infra/tests", "-t", "."],
  "done_when_text": "compose file parses and names postgres:16; .env.example has no values; secret grep finds a planted key in a temp tree and none in the repo; make test target exists"},

 {"id": "CMD-GC12", "role": "core-backend", "kind": "feature",
  "goal": "Backend core: app/core (settings from env names, psycopg pool, provenance enum, in-process event bus, log redaction filter), app/main.py create_app with /healthz, app/api router assembly that mounts each domain router, import-boundary test (domains import each other only via api.py).",
  "files": ["backend/app/__init__.py", "backend/app/main.py", "backend/app/core/**", "backend/app/api/**", "backend/tests/**"],
  "depends_on": ["CMD-GC10"],
  "interfaces": ["docs/architecture.md#3", "docs/security.md#2"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/tests", "-t", "backend"],
  "done_when_text": "healthz 200; redaction filter removes every pattern of data-model.md 4.1 from a log record; boundary test fails on a planted cross-domain service import; event bus delivers in order"},

 {"id": "CMD-GC13", "role": "core-backend", "kind": "feature",
  "goal": "Identity: signup, login, refresh (rotating, family reuse detection), logout, /v1/me; Argon2id; JWT 15 min; login rate limit; audit hooks via an injected recorder.",
  "files": ["backend/app/domains/identity/**"],
  "depends_on": ["CMD-GC12"],
  "interfaces": ["openapi: /v1/auth/*, /v1/me", "audit.api.record (fake until GC15)"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/identity/tests", "-t", "backend"],
  "done_when_text": "password never stored or returned; reused rotated refresh token revokes the family; expired JWT rejected; 11th login in 15 min refused"},

 {"id": "CMD-GC14", "role": "core-backend", "kind": "feature",
  "goal": "Workspace: workspaces, members, roles, projects; require_member(ws, user, min_role) used by every /v1/workspaces/{ws} route; personal workspace on identity.user.created.",
  "files": ["backend/app/domains/workspace/**"],
  "depends_on": ["CMD-GC13"],
  "interfaces": ["identity.api.current_user", "openapi: /v1/workspaces*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/workspace/tests", "-t", "backend"],
  "done_when_text": "non-member gets 404 on another workspace; viewer cannot create a project; user.created makes a personal workspace"},

 {"id": "CMD-GC15", "role": "core-backend", "kind": "feature",
  "goal": "Audit: append-only audit_log, record() and query() (admin only), GET /audit-log; detail is checked to carry no secret pattern.",
  "files": ["backend/app/domains/audit/**"],
  "depends_on": ["CMD-GC14"],
  "interfaces": ["workspace.api.require_member", "openapi: /v1/workspaces/{ws}/audit-log"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/audit/tests", "-t", "backend"],
  "done_when_text": "UPDATE/DELETE on audit_log raises; a detail with a key-shaped string is rejected; non-admin gets 403"},

 {"id": "CMD-GC16", "role": "core-backend", "kind": "feature",
  "goal": "Notification: in-app notifications and prefs; subscribers for quota.alert.raised, ingestion.job.finished/failed, advisor.proposal.created.",
  "files": ["backend/app/domains/notification/**"],
  "depends_on": ["CMD-GC15"],
  "interfaces": ["app.core.events", "openapi: /v1/notifications*, /v1/notification-prefs"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/notification/tests", "-t", "backend"],
  "done_when_text": "each subscribed event yields one notification; disabled pref suppresses it; mark read works"},

 {"id": "CMD-GC17", "role": "core-backend", "kind": "feature",
  "goal": "Quota: budgets in both measures (list, cli), burn series with P10/P50/P90 projection and exhaustion dates, threshold alerts once per threshold and period, quota.check(ws, scope, extra_cost) for the proposal gate.",
  "files": ["backend/app/domains/quota/**"],
  "depends_on": ["CMD-GC21"],
  "interfaces": ["usage.api.summary / daily totals", "openapi: /v1/workspaces/{ws}/budgets*, /quota/alerts"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/quota/tests", "-t", "backend"],
  "done_when_text": "used.list and used.cli both returned, cli coverage < 1000 when calls lack cli cost; 80% alert raised once; check() blocks an over-limit cost"},

 {"id": "CMD-GC20", "role": "ingestion-analytics", "kind": "feature",
  "goal": "Source: sources and uploads (multipart, sha256, size limit, object store path, purge_after), source.upload.stored event.",
  "files": ["backend/app/domains/source/**"],
  "depends_on": ["CMD-GC14"],
  "interfaces": ["workspace.api.require_member", "openapi: /v1/workspaces/{ws}/sources, /uploads"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/source/tests", "-t", "backend"],
  "done_when_text": "upload over GC_UPLOAD_MAX_BYTES gets 413; sha256 recorded; event emitted with ids only"},

 {"id": "CMD-GC21", "role": "ingestion-analytics", "kind": "feature",
  "goal": "Usage: load_calls (one transaction: calls, session/task totals, usage_daily), list-price costing in nano-USD from model_prices with version, models/prices seed (FINAL_TASK prices), and the chart queries: summary, token series, call-size histogram, compare (P10-P90 over tasks), calls/sessions/tasks pages, task PATCH emitting usage.task.outcome_set.",
  "files": ["backend/app/domains/usage/**"],
  "depends_on": ["CMD-GC14"],
  "interfaces": ["openapi: /v1/models, /v1/workspaces/{ws}/usage/*", "docs/data-model.md#2"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/usage/tests", "-t", "backend"],
  "done_when_text": "list cost of each FINAL_TASK ledger call, priced with the FINAL_TASK table (Haiku $1/$5, Sonnet $2/$10 per Mtok, cache writes x1.25, reads x0.1), equals its quota_usd within 1 micro-USD; reload is idempotent by dedupe_key; NULL tokens stay NULL; every series carries unit and provenance"},

 {"id": "CMD-GC22", "role": "ingestion-analytics", "kind": "feature",
  "goal": "Ingestion pipeline and worker: job state machine, SKIP LOCKED claim, retries, ingest_job_events with NOTIFY, SSE endpoint with Last-Event-ID replay, rejects without raw lines, usage.api.load_calls call.",
  "files": ["backend/app/domains/ingestion/**", "backend/app/worker/**"],
  "depends_on": ["CMD-GC20", "CMD-GC21"],
  "interfaces": ["source.api.open_upload", "usage.api.load_calls", "openapi: /v1/workspaces/{ws}/ingest-jobs*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/ingestion/tests", "-t", "backend"],
  "done_when_text": "two workers never claim one job; SSE resumes after Last-Event-ID without gaps; a failed job carries an error code and no content"},

 {"id": "CMD-GC23", "role": "ingestion-analytics", "kind": "feature",
  "goal": "Format adapters and scrub, reusing pinned parsers: Claude Code via telemetry.collect.from_cc_jsonl, ga L0 via telemetry.ledger.read_lenient, Anthropic/OpenAI usage CSV/JSON via a column map into telemetry.usage.l0_usage; context via rlo.usage_formats; secret scrub table; bodies dropped unless store_bodies.",
  "files": ["backend/app/domains/ingestion/adapters/**", "backend/app/domains/ingestion/scrub.py", "backend/app/domains/ingestion/tests/adapters/**", "fixtures/ingest/**"],
  "depends_on": ["CMD-GC22"],
  "interfaces": ["l0-telemetry@f6c7ae2", "rlo-sdk@0d92a3d", "docs/data-model.md#3"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/ingestion/tests/adapters", "-t", "backend"],
  "done_when_text": "each fixture format yields the expected UsageCall rows; no adapter defines its own JSONL/transcript parser; every scrub pattern is removed; no prompt body leaves the adapter by default"},

 {"id": "CMD-GC30", "role": "consulting", "kind": "feature",
  "goal": "Advisor: rules R1-R7 as deterministic detectors with the savings formulas of consulting.md 2, findings, proposals with the gate (policy -> quota.check -> confirm -> apply -> audit), decision endpoint.",
  "files": ["backend/app/domains/advisor/**"],
  "depends_on": ["CMD-GC21", "CMD-GC15", "CMD-GC17"],
  "interfaces": ["usage.api.calls/tasks", "quota.api.check", "audit.api.record", "fixtures/advisor/*.json", "openapi: /advisor/*, /proposals*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/advisor/tests", "-t", "backend"],
  "done_when_text": "each fixture's expect (evidence ids, p10/p50/p90 micro-USD) reproduced exactly; apply without confirm is refused; over-budget apply is blocked; every decision is audited"},

 {"id": "CMD-GC31", "role": "consulting", "kind": "feature",
  "goal": "Estimation: features, k-nearest evidence, weighted P10/P50/P90 for tokens/cost (both measures)/calls/duration, Laplace success probability, user blend, outcomes and MAPE; global prior from fixtures/final_task; backtest_estimator.py gains --estimator app and must beat the baseline MAPE.",
  "files": ["backend/app/domains/estimation/**", "scripts/backtest_estimator.py"],
  "depends_on": ["CMD-GC21"],
  "interfaces": ["usage.api.tasks", "openapi: /estimates*, /estimation/accuracy"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/estimation/tests", "-t", "backend"],
  "done_when_text": "app estimator token MAPE on FINAL_TASK LOO < baseline 21.98% and P10-P90 coverage >= 70%; fewer than 3 evidence widens the range; estimate never stores description text"},

 {"id": "CMD-GC32", "role": "consulting", "kind": "feature",
  "goal": "Profile: profile CRUD (store_bodies default false), personal_stats refresh on usage events, recommendations with evidence >= 5 and quality floor, hand-off to advisor.submit_proposal.",
  "files": ["backend/app/domains/profile/**"],
  "depends_on": ["CMD-GC21"],
  "interfaces": ["usage.api.tasks", "advisor.api.submit_proposal (fake until GC30)", "openapi: /profile*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/profile/tests", "-t", "backend"],
  "done_when_text": "stats match hand-computed per-correct cost on a fixture; no recommendation below quality floor or with < 5 evidence; another user's stats never returned"},

 {"id": "CMD-GC33", "role": "consulting", "kind": "feature",
  "goal": "Simulation: what-if for model_swap, context_cap (rlo.ctxbudget.simulate), node_count, cache_prefix_fixed, structure; assumptions and basis recorded on every result; to_proposal.",
  "files": ["backend/app/domains/simulation/**"],
  "depends_on": ["CMD-GC31"],
  "interfaces": ["usage.api.calls", "profile.api.stats", "advisor.api.submit_proposal", "openapi: /simulations*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/simulation/tests", "-t", "backend"],
  "done_when_text": "empty assumptions -> 422; every result has provenance SIMULATED and basis with price_version; model_swap on identical prices changes cost by 0"},

 {"id": "CMD-GC34", "role": "consulting", "kind": "feature",
  "goal": "Report: period report (usage, savings from findings, budget status, next-period settings) and JSON/CSV export; numbers keep provenance.",
  "files": ["backend/app/domains/report/**"],
  "depends_on": ["CMD-GC30", "CMD-GC17"],
  "interfaces": ["usage.api.summary", "advisor.api.list_findings", "quota.api.burn", "openapi: /reports*"],
  "done_when": ["python3", "-m", "unittest", "discover", "-s", "backend/app/domains/report/tests", "-t", "backend"],
  "done_when_text": "CSV and JSON exports agree; every number has a provenance column; export is audited"},

 {"id": "CMD-GC40", "role": "frontend", "kind": "feature",
  "goal": "Frontend shell: Next.js app, auth pages, workspace switcher, typed API client generated from docs/api/openapi.yaml, fake API for screens, ECharts theme, provenance chip and money/token formatters, file-system route registry so screens add no shared nav edits.",
  "files": ["frontend/package.json", "frontend/tsconfig.json", "frontend/next.config.mjs", "frontend/src/app/layout.tsx", "frontend/src/app/page.tsx", "frontend/src/app/(auth)/**", "frontend/src/lib/**", "frontend/src/components/**", "frontend/tests/shell/**"],
  "depends_on": ["CMD-GC10"],
  "interfaces": ["docs/api/openapi.yaml", "docs/visualization.md#출처 표시"],
  "done_when": ["npm", "--prefix", "frontend", "run", "test", "--", "--run", "tests/shell"],
  "done_when_text": "client types compile from openapi.yaml; chip renders each provenance; formatter turns 1234 micro-USD into $0.0012; null renders as an em dash"},

 {"id": "CMD-GC41", "role": "frontend", "kind": "feature",
  "goal": "Usage screens: overview, token_mix, call_size exactly as docs/visualization.md (API, series, units, provenance styling).",
  "files": ["frontend/src/app/(app)/overview/**", "frontend/src/app/(app)/token-mix/**", "frontend/src/app/(app)/call-size/**", "frontend/tests/usage/**"],
  "depends_on": ["CMD-GC40"],
  "interfaces": ["openapi: /usage/summary, /usage/series/tokens, /usage/series/call-size, /usage/calls, /budgets"],
  "done_when": ["npm", "--prefix", "frontend", "run", "test", "--", "--run", "tests/usage"],
  "done_when_text": "each screen calls only its listed paths (fake API spy); both cost measures shown side by side; cli coverage chip appears below 100%"},

 {"id": "CMD-GC42", "role": "frontend", "kind": "feature",
  "goal": "Consulting screens: config_compare, budget_burn, findings + proposals with confirm dialog, estimate form with self-measured MAPE, what-if with assumption list, profile.",
  "files": ["frontend/src/app/(app)/compare/**", "frontend/src/app/(app)/budgets/**", "frontend/src/app/(app)/advisor/**", "frontend/src/app/(app)/estimate/**", "frontend/src/app/(app)/what-if/**", "frontend/src/app/(app)/profile/**", "frontend/tests/consulting/**"],
  "depends_on": ["CMD-GC40"],
  "interfaces": ["openapi: /usage/compare, /budgets/{budget}/burn, /advisor/findings, /proposals*, /estimates, /estimation/accuracy, /simulations, /profile*"],
  "done_when": ["npm", "--prefix", "frontend", "run", "test", "--", "--run", "tests/consulting"],
  "done_when_text": "ESTIMATED drawn dashed with P10-P90 band; SIMULATED shows its assumptions; apply requires an explicit confirm step"},

 {"id": "CMD-GC43", "role": "frontend", "kind": "feature",
  "goal": "Ingestion and ops screens: upload with live SSE progress (resume on reconnect), notifications, audit log (admin).",
  "files": ["frontend/src/app/(app)/upload/**", "frontend/src/app/(app)/notifications/**", "frontend/src/app/(app)/audit/**", "frontend/tests/ops/**"],
  "depends_on": ["CMD-GC40"],
  "interfaces": ["openapi: /uploads, /ingest-jobs/{job}/events (SSE), /v1/notifications*, /audit-log"],
  "done_when": ["npm", "--prefix", "frontend", "run", "test", "--", "--run", "tests/ops"],
  "done_when_text": "progress bar follows a scripted SSE stream and resumes with Last-Event-ID; audit page hidden for non-admin"}
]
```

## 5. 나중 (설계만, 작업 항목 없음)

- Run 도메인: runner 프로세스(ga 0.6 노드 풀), `runs*` API, 화면 node_timeline · task_flow · peer_network · verdicts. 시작은 Proposal 승인 뒤.
- integration: 공급자 키 봉투 암호화(ADR-0007), 공급자 API 자동 연동, GitHub · Slack.
- 팀 권한 세분화(프로젝트별), 공개 API, 벤치마크(FINAL_TASK 형식), 주간 리포트 PDF, 결제.
