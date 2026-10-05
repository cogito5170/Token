# 파일 소유표

저장소의 **모든 파일은 아래 패턴 중 정확히 하나**에 맞는다(`scripts/check_docs.py` 가 `.git`, `.venv`, `node_modules`, `__pycache__`, `.next` 를 뺀 모든 파일로 검사한다). 패턴 문법: `**` = 아무 경로(슬래시 포함), `*` = 슬래시 없는 아무 글자.

- `role`: design · frontend · core-backend · ingestion-analytics · consulting · infra 중 하나(design 은 사양 7.1, 2026-10-05 추가). `baseline` 은 이 저장소의 작업 항목이 쓰지 않는 파일(사양 · 세션 보고)이다.
- `contract = yes`: 공유 계약. `"kind": "contract"` 작업만 이 파일을 `files` 에 넣을 수 있다. 다른 작업은 읽기만 한다.
- 작업 항목(roadmap.md)의 `files` 는 자기 role 의 행 안에 있어야 한다. 서로 의존 관계가 없는 두 작업은 같은 파일을 가질 수 없다.

| pattern | role | contract |
|---|---|---|
| `docs/00-product-spec.md` | baseline | no |
| `reports/**` | baseline | no |
| `STATE.md` | baseline | no |
| `docs/architecture.md` | core-backend | yes |
| `docs/domain-model.md` | core-backend | yes |
| `docs/data-model.md` | core-backend | yes |
| `docs/api-contract.md` | core-backend | yes |
| `docs/api/**` | core-backend | yes |
| `docs/schema.sql` | core-backend | yes |
| `docs/visualization.md` | core-backend | yes |
| `docs/consulting.md` | core-backend | yes |
| `docs/security.md` | core-backend | yes |
| `docs/roadmap.md` | core-backend | yes |
| `docs/ownership.md` | core-backend | yes |
| `docs/adr/**` | core-backend | yes |
| `scripts/check_docs.py` | core-backend | yes |
| `scripts/validate_openapi.py` | core-backend | yes |
| `scripts/export_work.py` | core-backend | yes |
| `scripts/vendor/**` | core-backend | yes |
| `tests/**` | core-backend | yes |
| `fixtures/advisor/**` | core-backend | yes |
| `backend/pyproject.toml` | core-backend | yes |
| `backend/migrations/**` | core-backend | yes |
| `backend/app/domains/__init__.py` | core-backend | yes |
| `backend/app/__init__.py` | core-backend | no |
| `backend/app/main.py` | core-backend | no |
| `backend/app/core/**` | core-backend | no |
| `backend/app/api/**` | core-backend | no |
| `backend/tests/**` | core-backend | no |
| `backend/app/domains/identity/**` | core-backend | no |
| `backend/app/domains/workspace/**` | core-backend | no |
| `backend/app/domains/quota/**` | core-backend | no |
| `backend/app/domains/notification/**` | core-backend | no |
| `backend/app/domains/audit/**` | core-backend | no |
| `backend/app/domains/integration/**` | core-backend | no |
| `backend/app/domains/run/**` | core-backend | no |
| `backend/app/domains/source/**` | ingestion-analytics | no |
| `backend/app/domains/ingestion/**` | ingestion-analytics | no |
| `backend/app/domains/usage/**` | ingestion-analytics | no |
| `backend/app/worker/**` | ingestion-analytics | no |
| `fixtures/ingest/**` | ingestion-analytics | no |
| `backend/app/domains/estimation/**` | consulting | no |
| `backend/app/domains/advisor/**` | consulting | no |
| `backend/app/domains/simulation/**` | consulting | no |
| `backend/app/domains/profile/**` | consulting | no |
| `backend/app/domains/report/**` | consulting | no |
| `scripts/backtest_estimator.py` | consulting | no |
| `fixtures/final_task/**` | consulting | no |
| `design/**` | design | no |
| `docs/ui-design.md` | design | yes |
| `docs/ui/**` | design | yes |
| `frontend/**` | frontend | no |
| `fixtures/monitor/**` | core-backend | no |
| `desktop/**` | infra | no |
| `infra/**` | infra | no |
| `.github/**` | infra | no |
| `Makefile` | infra | no |
| `README.md` | infra | no |
| `.env.example` | infra | no |
| `.gitignore` | infra | no |
| `scripts/dev_env.py` | infra | no |
| `scripts/e2e_stack.py` | infra | no |

## 도메인 → 역할 (요약)

| 도메인 | 역할 |
|---|---|
| identity · workspace · quota · notification · audit · integration · run (모니터 리더 포함) | core-backend |
| source · ingestion · usage | ingestion-analytics |
| estimation · advisor · simulation · profile · report | consulting |

`fixtures/advisor/**` 는 advisor 규칙의 기대값(계약)이라 contract 이다. 규칙 구현(consulting)은 이것을 읽고 맞춘다.

시각 언어(`design/**`: 토큰 · 신호 대응표 · 움직임 규칙 · golden 장면)는 design 역할이 소유하고, frontend 는 읽기만 한다. `docs/ui-design.md` 와 `docs/ui/**` 는 frontend 가 따르는 계약이라 contract 다.
