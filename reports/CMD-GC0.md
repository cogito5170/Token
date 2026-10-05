```ga
{"schema":"report/2","from":"ARCH","handled":[{"id":"CMD-GC0","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/arch-phase0","sha":"7a59e14f7d8a4aa30c7704bba21c1ff2d5e32033"}],"tests":{"passed":30,"failed":0,"skipped":0},"change_size":"interface","items":[{"id":"D1","state":"met","evidence":["python3 scripts/check_docs.py -> check_docs: 0 problem(s)","python3 scripts/validate_openapi.py -> 61 paths, 74 operations, 0 problems (official OAS 3.1 structural schema, OAI v3.1-dev@551e3df1, vendored + JSON Schema 2020-12 per component + $ref/operationId/path-param checks)","docs/schema.sql applied with psql -v ON_ERROR_STOP=1 to an empty PostgreSQL 16 database: 43 tables (41 + ga_dirs, monitor_recordings); tests/test_schema.py also checks the audit_log append-only trigger","make test: 26 root tests + 4 backend skeleton tests OK (GC_SCHEMA_TEST_DSN set, so 0 skipped)","python3 scripts/backtest_estimator.py: 100 valid runs (12 void excluded); baseline (group median, leave-one-out) MAPE tokens 21.98%, cost 92.68%, P10-P90 coverage 64%/65%; naive global median 67.68%/249.60%"]},{"id":"D2","state":"met","evidence":["tests/test_check_docs.py on a copy of the repo: domain row removed from architecture.md -> caught; usage_calls added to quota's owned_tables (two owners) -> caught; x-domain removed from /quota/alerts -> caught; token_mix api pointed at a missing path -> caught; R3 fixture deleted and R5 fixture line removed -> caught","8 more mutations caught: domain missing from ownership.md, table with no owner, screen with wrong method, unowned file, work item file outside its role, contract file in a feature item, two independent items sharing files","additions: an L0 kind removed from design/encoding.json, a ga-emitted signal encoded as none, an on-stage word outside build/wait/talk/test/done, a low-contrast token, a missing wireframe, a work item without runner, the live_monitor screen removed -> all caught"]},{"id":"D4","state":"met","evidence":["baseline additions 1-4 (spec 3.1, 3.1.1, 7.1 at 6259ea2, merged into the branch): visualization.md screen 10 live_monitor; Run domain monitor read model (data-model.md 7, ga_dirs + monitor_recordings, /monitor/sources* GET + SSE + recordings); ADR-0008 Electron + read-only Python sidecar; ADR-0009; docs/ui-design.md, design/tokens.json, design/encoding.json (47 signals: 29 L0 kinds + 13 file + 5 derived), design/motion.md, docs/ui/wireframes.md (10 screens + estimate); design role in ownership.md and roadmap.md; 28 work items with runner (unittest/vitest/playwright), incl. CMD-DS1-3, CMD-FE1 component library (Playwright visual tests), CMD-RN1, CMD-FE2, CMD-IF1","check_docs.py: every L0 kind (ga 0.6 emitted 8 + l0-telemetry catalog) and every live_monitor signal has a visual encoding; token contrast computed with the WCAG formula","baseline verdict @df31d9a: needs moved to prose 'baseline 요청'; integration branch (spec 6259ea2) merged with a merge commit; export_work.py prints a clear error and exits 2 on an unknown depends_on (tests/test_scripts.py)"]},{"id":"D3","state":"met","evidence":["this report; notify/1 sent to baseline with the report commit sha"]}],"deviations":["pip install of ga-sdk[net] was refused in this session by the permission classifier, so `python -m ga judge --template` and `python -m ga check reports/CMD-GC0.md` were not run; this head was written by hand from ga/specs/forms/report2.pspec and reports/CMD-GA31.md at ga-sdk 03e8dae","the commits sha is the last content commit; the report itself is the next commit on the same branch","container Python is 3.11; the skeleton targets 3.12 but its tests run on 3.11","baseline requests are in the prose section 'baseline 요청' (report/2 needs takes only credential, budget, new_repo, new_session)"],"note":"Architecture, contracts, UI design contract, live monitor design and 28 work items on claude/arch-phase0; no feature code."}
```

# CMD-GC0 보고 — ga Console 0 단계 (아키텍처)

## 한 일

사양(`docs/00-product-spec.md`, 고치지 않음)을 구현 구조와 계약으로 옮겼다. 사양 8 절의 도메인 15 개를 각각 책임 · 소유 테이블 · 공개 인터페이스 · 이벤트 · 금지 사항으로 고정했고, 그 위에 DB 스키마, OpenAPI 3.1 계약(MVP 의 SSE 는 수집 작업 진행, Run 은 `x-later`), 정규화 사용 모델과 수집 파이프라인, 두 기준 쿼터, 견적 · advisor · 개인화 · What-if 모델, 화면 9 개의 시각화 계약, 안전 규칙, 28 개 작업 항목의 병렬 계획과 파일 소유표를 썼다. 이 문서들 사이의 일관성은 표준 라이브러리만 쓰는 `scripts/check_docs.py` 가 결정적으로 검사하고, 시험은 D2 의 변이를 모두 잡는다. 견적기 기준선 숫자도 만들었다: FINAL_TASK fixture 에서 그룹 중앙값 leave-one-out MAPE 는 토큰 21.98 %, 비용 92.68 %다. 이후 견적기는 이 숫자를 이겨야 한다.

주요 결정:
- modular monolith (FastAPI, 도메인당 패키지 하나, 다른 도메인은 `api.py` 로만 부른다), PostgreSQL 하나에 큐까지(`SKIP LOCKED`), ECharts, SSE.
- 금액은 정수 micro-USD. 호출 행만 nano-USD 로 둬서 FINAL_TASK 의 $0.0005 호출을 반올림 없이 담는다. 비용은 항상 두 열이다: `cost_list` (CALCULATED) 와 `cost_cli` (MEASURED, 없으면 NULL + 커버리지).
- 모든 원천은 먼저 l0-telemetry 의 L0 이벤트로 바뀐다(`from_cc_jsonl`, `ledger.read_lenient`, `l0_usage`). 새 파서는 쓰지 않는다. 공급자 내보내기는 열 매핑 어댑터만 쓴다.
- advisor 규칙 7 개는 각각 탐지기 경로, 정확한 절감식(P10/P50/P90), fixture 를 가진다. fixture 의 기대값은 유리수로 계산해 마지막에 한 번 내림했으므로 구현이 그대로 재현할 수 있다.
- AI 출력은 모두 Proposal 이다. 적용 순서는 정책 → `quota.check` → `confirm` → 실행 → 감사이고, MVP 의 "적용"은 내보내기와 플랫폼 안 설정뿐이다.

## 추가 지시 (baseline, 같은 지시 안)

- **라이브 워크플로 모니터 (사양 3.1 · 3.1.1):**
  - visualization.md 화면 10 이다. 움직이는 장면 하나이고, 페이지 · 탭 · 표가 없다.
  - 장면 요소: figure · tile · 펄스 · 선 굵기(π) · 결과 고리 · 연료 호, 그리고 분위기(속도 · 막힘 · 협업 · 긴장 · 완료).
  - 글자는 build · wait · talk · test · done 다섯 단어뿐이고, 숫자는 호버 때만 보인다.
- **신호 대응표 `design/encoding.json`:**
  - 신호 47 개 = L0 종류 29(ga 0.6 이 내는 8 + l0-telemetry 카탈로그) + `.ga` 파일 신호 13 + 파생 분위기 5.
  - 각 신호에 움직임, 움직임 줄이기 형태, 색이 아닌 단서를 적었다.
  - `check_docs.py` 가 빠짐을 잡는다.
- **Run 도메인 (1b):**
  - `.ga` 를 읽기만 하는 리더를 둔다. 읽는 것: pool.json, queue/, nodes/*/run.json · state.json · pi.json · ga-budget.jsonl, L0, usage.json.
  - 리더는 `monitor-event/1` 와 관측 시각 · 스냅샷 · SSE · 녹화를 낸다. 녹화 재생은 결정적이다.
  - 조작 엔드포인트는 없다.
- **데스크톱:** ADR-0008 에서 Electron 을 골랐다.
  - 애니메이션이 웹과 같은 Chromium 에서 그려지고, Playwright 로 같은 golden 을 검사할 수 있다.
  - Tauri 는 시스템 WebView 차이 때문에 고르지 않았다. 특히 WebKitGTK 의 canvas 성능이 문제다.
  - 로컬 `.ga` 는 같은 Python 리더를 127.0.0.1 사이드카로 띄워 읽는다. 리더 구현이 하나라 웹과 데스크톱이 어긋나지 않는다.
- **UI 디자인 계약:**
  - `docs/ui-design.md` 에 원칙을 적었다: 질문 = 제목, 숫자 → 차트 → 근거 순서, 강조색 하나, 밝은 테마 기본 · 모니터는 어두운 테마, AA 대비, 파랑/주황, tabular 숫자, 움직임 줄이기.
  - 내비 묶음은 사용 현황 / 실행 / 컨설팅이다.
  - 토큰 원본은 `design/tokens.json` 이다(글꼴 IBM Plex Sans KR + Plex Mono, 대비와 휘도 차는 자동 검사).
  - 출처 칩은 선 모양으로 구분한다: 꽉 참 / 테두리 / 파선 / 점선.
  - 와이어프레임은 `docs/ui/wireframes.md` 다(모니터와 견적은 자세히).
- **design 역할:**
  - 소유표와 작업 목록에 넣었다. DS1 토큰, DS2 신호 대응표 · 움직임, DS3 golden 장면이다.
  - frontend 작업으로 FE1 공유 컴포넌트(Playwright 시각 시험)와 FE2 모니터 화면, infra 작업으로 IF1 데스크톱 셸을 넣었다.
- **baseline 참고 반영:**
  - MVP 는 먼저 hub 방식으로 만들고, 노드 풀은 ga 기능이 생긴 뒤에 쓴다.
  - work/1 에 없어도 `depends_on` · `files` 는 목록에 그대로 둔다.
  - 작업마다 `runner` 를 적었고, id 는 `ga work add` 형식이다.
- **ga 0.6 L0 의 한계 (baseline 요청 6–9):**
  - turn.started 와 턴 안 진행 이벤트가 없어서, 턴은 "running (elapsed)" 로만 보인다(ga-budget.jsonl 증가 기준).
  - L0 에 시각이 없어서 모니터가 관측 시각을 찍는다.
  - pool 모드에는 작업별 판정 이벤트가 없고, 노드 상태도 파일에 남지 않는다.
  - ga-sdk 는 바꾸지 않았다.

## 바꾼 파일

- docs: `architecture.md`, `domain-model.md`, `data-model.md`, `schema.sql`, `api/openapi.yaml`, `api-contract.md`, `visualization.md`, `consulting.md`, `security.md`, `roadmap.md`, `ownership.md`, `adr/0001`–`0007`
- 추가분: `docs/ui-design.md`, `docs/ui/wireframes.md`, `docs/adr/0008`–`0009`, `design/tokens.json` · `encoding.json` · `motion.md`, visualization · domain-model · data-model · schema · openapi · api-contract · security · roadmap · ownership 갱신, 사양 6259ea2 병합(사양 파일은 고치지 않음)
- scripts: `check_docs.py` (stdlib), `validate_openapi.py` (+ `vendor/oas-3.1-schema.yaml`), `backtest_estimator.py` (stdlib), `export_work.py` (roadmap → work/1)
- fixtures: `final_task/` (ga-sdk 03e8dae `bench/final_task/results` 의 결과 파일 4 개를 바꾸지 않고 복사, `SOURCE.md` 에 출처), `advisor/R1`–`R7.json`
- 뼈대: `backend/` (도메인 패키지 15 개는 `DOMAIN` 과 `OWNED_TABLES` 만 가짐, core 의 provenance · config 이름, pyproject 에 ga-sdk/rlo/l0-telemetry 를 `_pins.py` 와 같은 URL · sha 로 고정), `tests/`, `frontend/`, `infra/`, `Makefile`, `.env.example` (값 없음), `.gitignore`, `README.md`

## 돌린 시험과 결과

- `python3 scripts/check_docs.py` → 0 problems.
- `python3 scripts/validate_openapi.py` → 경로 61 개, 연산 74 개, 0 problems. 일부러 깨뜨린 문서(잘못된 `$ref`, 모르는 최상위 키, `openapi: 2.0`)는 잡힌다.
- 빈 PostgreSQL 16 에 schema.sql 적용 → 테이블 43 개, audit_log 의 UPDATE 는 트리거가 거부한다.
- `make test` (GC_SCHEMA_TEST_DSN 설정) → root 26 + backend 4 = 30 통과, 0 skip.
- `python3 scripts/backtest_estimator.py` → 위의 MAPE.

## 남은 문제

- **설치 거부:** 이 세션에서 `pip install ga-sdk[net]` 가 권한 분류기에 막혔다. 그래서 `ga judge --template` · `ga check` 를 돌리지 못했고, report/2 머리는 pspec 과 CMD-GA31 예시를 보고 손으로 썼다. 의존성 고정(pyproject)이 실제로 풀리는지도 확인하지 못했다. 설치가 허용된 세션에서 `pip install -e backend[dev]` 와 `ga check reports/CMD-GC0.md` 를 한 번 돌려야 한다.
- FINAL_TASK 의 가격표(Haiku $1/$5, Sonnet $2/$10)는 시험용 seed 다. 운영 가격은 `model_prices` 에 데이터로 넣는다.
- Claude Code transcript 의 CLI 비용은 세션 단위(cost-state)다. 그래서 R6(실행기 오버헤드)은 호출 단위로는 ga ledger 에서만 정확하다(baseline 요청 3).
- backend 작업의 done_when 은 FastAPI 등 런타임 의존성이 설치돼야 돌고, frontend 작업은 GC40 이 vitest 를 설치한 뒤에 돈다.
- check_docs 의 OpenAPI 읽기는 줄 단위이고 지금 서식(들여쓰기 2 칸)에 의존한다. 완전한 파싱은 validate_openapi(PyYAML + jsonschema, dev extra)가 한다.

## baseline 요청

이 저장소에서 우회하지 않고 baseline 에 올리는 요청이다(ga-sdk · l0-telemetry · rlo 쪽 작업).

1. l0-telemetry: parsers for provider usage exports (Anthropic console usage CSV/JSON, OpenAI usage export) emitting L0 events; until then ingestion keeps only a column map into telemetry.usage.l0_usage
2. l0-telemetry: a general secret scrubber (pattern table) for strings; until then backend/app/domains/ingestion/scrub.py holds the table
3. l0-telemetry/ga: per-call timestamps (`at`) in from_cc_jsonl output and in ga run.end (l0.py writes at=null), and per-call CLI cost for Claude Code transcripts (cost-state is per session)
4. ga-sdk: a public, versioned export/import of router `learn` stats (ga-node-router/1) so per-user stats can seed a node's router later
5. rlo: full per-call collectors for Codex and Gemini CLI logs (readers return only the last usage)
6. ga-sdk (live monitor): a turn.started event and intra-turn progress events (relay of the runner's stream-json as l0-telemetry tool.start/tool.end/llm.request/llm.response); until then the monitor shows turns as running (elapsed) from ga-budget.jsonl growth
7. ga-sdk (live monitor): wall-clock `at` on every L0 event (ga 0.6 writes at=null; pool events also lack id/run_id/seq), so replay and elapsed time do not depend on the reader's observation time
8. ga-sdk (live monitor): per-item check/verdict events in pool mode (verdict/1 exists only in hub mode, inside round records), and the node step outcome persisted in run.json (idle/waiting/done/check_failed is returned but not written)
9. ga-sdk: atomic write of .ga/usage.json (plain write_text today)

## 다음 세션이 알아야 할 것

1. 시작은 `python3 scripts/export_work.py` 다. 출력은 의존 순서대로 된 work/1 28 줄이다. 지금은 hub 지시문으로 하나씩 넣고, 노드 풀은 ga 기능이 생긴 뒤에 쓴다. 첫 물결은 GC10 · DS1, 다음은 GC11 · GC12 · GC40 · DS2 다. 역할은 design · frontend · core-backend · ingestion-analytics · consulting · infra 6 개다.
2. 각 작업은 `docs/ownership.md` 에서 자기 role 행 안의 파일만 바꾼다. contract 파일(openapi.yaml, schema.sql, domain-model.md, visualization.md, consulting.md, fixtures/advisor, migrations, pyproject, tests/)은 `kind: contract` 작업만 바꾼다. 바꾼 뒤에는 `make check` 와 `make test` 가 통과해야 한다.
3. advisor 구현(GC30)은 `fixtures/advisor/*.json` 의 `expect` 를 정확히 재현해야 한다(Fraction, nano-USD, 마지막에 한 번 내림).
4. 견적기(GC31)는 `backtest_estimator.py` 기준선(토큰 MAPE 21.98 %)을 이겨야 한다.
5. 모니터 작업(RN1 · DS3 · FE2)은 `design/encoding.json` 의 신호 이름이 계약이다. 재생 결정성은 `scene(events, t)` 순수 함수로 지킨다.
6. baseline 요청 9 건은 위 'baseline 요청' 절에 있다. 이 저장소에서 우회 구현을 파서로 키우지 않는다.
