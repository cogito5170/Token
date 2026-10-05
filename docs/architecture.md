# ga Console 아키텍처

상태: CMD-GC0 (0 단계) 확정본. 원천 사양은 `docs/00-product-spec.md` 이며 이 문서는 그것을 구현 구조로 옮긴다. 사양과 충돌하면 사양이 이긴다.

## 1. 한 장 요약

ga Console 은 사용자의 AI 사용 기록을 받아 **정규화 → 분석 → 시각화 → 컨설팅** 하는 토큰 서비스 플랫폼이다. ga-sdk 를 바꾸지 않고, ga-sdk · l0-telemetry · rlo 를 **고정 sha 의존성**으로 쓴다(ADR-0004).

```
 브라우저 (Next.js, ECharts)                        ← SSE: 수집 작업 진행 (MVP), ga 실행 (나중)
      │  HTTPS JSON  /v1/...   (docs/api/openapi.yaml)
      ▼
 ┌──────────────── backend (FastAPI, modular monolith, Python 3.12) ───────────────┐
 │  app/api  ── 라우터: 경로마다 x-domain 하나                                        │
 │  app/domains/<domain>/  ── 도메인 패키지 15 개 (아래 표). 서로 public 인터페이스로만  │
 │  app/core/  ── 설정 · DB 세션 · 인증 미들웨어 · 이벤트 버스 · 출처(provenance) 타입  │
 └──────────────┬────────────────────────────────────────┬────────────────────────┘
                │ SQL (PostgreSQL 16)                    │ job 큐 (PostgreSQL 테이블, SKIP LOCKED)
                ▼                                        ▼
         PostgreSQL ◄──────────────────────────── worker (app/worker)
         (docs/schema.sql)                         업로드 → 파싱(l0-telemetry/rlo) → 정규화
                                                   → 비밀값 제거 → usage 적재 → 분석(advisor, quota)
```

- **프로세스 2 종:** `api`(FastAPI, uvicorn), `worker`(같은 코드베이스, `python -m app.worker`). 둘 다 같은 도메인 패키지를 쓴다.
- **저장소 1 종:** PostgreSQL. 큐도 PostgreSQL 테이블(`ingest_jobs`)로 시작한다(ADR-0003). 업로드 원본은 객체 저장소 경로(로컬 디스크 → S3 호환)로 두고 DB 에는 메타데이터만.
- **실시간:** SSE. MVP 에서는 수집 작업 진행 이벤트(`ingest_job_events`)만 흐른다. ga 실행 스트림(Run 도메인)은 설계만 하고 **나중**으로 표시한다.

## 2. 도메인 (사양 8 절)

모든 도메인은 `backend/app/domains/<domain>/` 패키지 하나다. 책임 · 소유 테이블 · 공개 인터페이스 · 이벤트 · 금지 사항은 `docs/domain-model.md` 에 있다. 아래 표의 도메인 id 는 `scripts/check_docs.py` 가 기준으로 쓴다.

| 도메인 id | 이름 | 한 줄 책임 | MVP | 주 담당 역할 |
|---|---|---|---|---|
| `identity` | Identity | 가입 · 로그인 · 토큰 갱신 · 비밀번호 해시 | MVP | core-backend |
| `workspace` | Workspace | 워크스페이스 · 구성원 · 프로젝트 · 역할 | MVP | core-backend |
| `source` | Source | 기록 출처(업로드 · 연결) 등록과 원본 파일 메타데이터 | MVP | ingestion-analytics |
| `ingestion` | Ingestion | 수집 작업: 파싱 → 비밀값 제거 → 정규화 → 적재, 진행 이벤트 | MVP | ingestion-analytics |
| `usage` | Usage | 정규화 사용 모델(호출 · 세션 · 작업 · 모델 · 캐시 · 비용), 가격표, 집계 시계열 | MVP | ingestion-analytics |
| `quota` | Quota | 예산 · 두 기준 쿼터 · 소진 예측 · 예산 경보 | MVP | core-backend |
| `estimation` | Estimation | 실행 전 견적(P10/P50/P90, 근거, 자체 오차) | MVP | consulting |
| `advisor` | Advisor | 낭비 규칙 7 종 → 발견(finding) → Proposal, Proposal 승인 흐름 | MVP | consulting |
| `simulation` | Simulation | What-if: 가정 기록 + 과거 데이터 재계산 | MVP(기본) | consulting |
| `profile` | Profile | 개인 프로필 · 사용자별 라우터/견적 통계 · 맞춤 추천 | MVP | consulting |
| `report` | Report | 기간 리포트 생성 · 내보내기(CSV · JSON, PDF 는 나중) | MVP(기본) | consulting |
| `notification` | Notification | 앱 내 알림 · 이메일(나중: Slack) | MVP(앱 내) | core-backend |
| `audit` | Audit | 승인 · 실행 · 설정 변경의 추가 전용 감사 로그 | MVP | core-backend |
| `integration` | Integration | 외부 연동(GitHub · Slack) · 공급자 키 암호 보관 | 나중(스키마만) | core-backend |
| `run` | Run | 플랫폼 안 ga 실행 · 노드 · 판정 (나중) | 나중 | core-backend |

## 3. 도메인 간 규칙

1. **소유:** 테이블은 정확히 한 도메인이 소유한다. 다른 도메인은 그 테이블을 직접 쓰지 않는다. 읽기도 원칙적으로 소유 도메인의 public 인터페이스(`app/domains/<d>/api.py` 의 함수 · 읽기 전용 view)로 한다.
2. **의존 방향:** `identity ← workspace ← (source, ingestion, usage) ← (quota, estimation, advisor, simulation, profile) ← (report, notification)`. `audit` 은 모두가 호출하지만 아무것도 부르지 않는다. 역방향 호출은 이벤트로만 한다.
3. **이벤트:** 도메인 이벤트는 `app/core/events.py` 의 동기 in-process 버스 + `domain_events` 아웃박스(트랜잭션과 같이 커밋)로 전달한다. 이벤트 이름은 `<domain>.<noun>.<verb-past>` (예: `usage.calls.ingested`). 목록은 domain-model.md.
4. **화면은 원본 테이블을 읽지 않는다:** 프런트엔드는 openapi.yaml 의 경로만 부른다. 차트용 경로는 집계 · 출처 표시가 끝난 시리즈를 돌려준다(visualization.md).
5. **AI 는 결정권자가 아니다:** advisor · simulation · (나중) run 노드의 출력은 모두 `Proposal` 이다. 적용은 Proposal → 정책 검사 → 예산 검사 → 사용자 확인 → 실행 → 감사 기록 순서로만 일어난다(security.md 4 절).

## 4. 출처(provenance) 표시

모든 숫자 값은 출처 하나를 가진다. 타입은 `app/core/provenance.py` 의 enum 이고 API 에서는 `provenance` 필드다.

| 값 | 뜻 | 예 |
|---|---|---|
| `MEASURED` | 외부가 보고한 원값 | 공급자 `usage` 토큰, `claude -p` 의 `total_cost_usd` |
| `CALCULATED` | 측정값에 결정적 계산을 한 값 | 정가표로 환산한 비용, 일별 합계, 맞힌 작업당 비용 |
| `ESTIMATED` | 통계 모델의 예측 | 견적 P10/P50/P90, advisor 의 절감 추정 |
| `SIMULATED` | 사용자가 준 가정 아래 다시 계산한 값 | What-if 결과 |

규칙: 출처가 다른 두 값을 더하지 않는다. 합치면 결과의 출처는 더 약한 쪽(MEASURED > CALCULATED > ESTIMATED > SIMULATED)이다.

## 5. 쿼터 두 기준

FINAL_TASK 교훈(CLI 비용이 usage 정가 환산보다 평균 1.91 배): 비용은 항상 두 열로 저장 · 표시한다.

- `cost_list_nanousd` (CALCULATED, 호출 행) / `cost_list_microusd` (집계): usage 토큰 × 정가표(`model_prices`). 캐시 쓰기 ×1.25(5m) / ×2(1h), 캐시 읽기 ×0.1 은 가격표의 행으로 둔다.
- `cost_cli_microusd` (MEASURED): CLI 가 보고한 비용(`total_cost_usd`, transcript 의 cost-state). 없으면 NULL — 0 으로 채우지 않는다.
- 금액은 정수 **micro-USD**(1e-6 USD; 호출 행의 정가 환산만 nano-USD 로 반올림 오차를 피한다), 토큰은 정수다(ADR-0001).

## 6. 수집 파이프라인 (요약, 자세히는 data-model.md 4 절)

```
upload/source → ingest_job(queued) → worker claim
  → detect format → parse (기존 파서) → scrub → normalize(UsageCall) → dedupe → load usage_calls
  → rollup usage_daily → emit usage.calls.ingested → quota/advisor/profile 재계산 → job done
```

| 입력 | 파서 (재사용) | 비고 |
|---|---|---|
| Claude Code transcript `.jsonl` | `telemetry.collect.from_cc_jsonl` → `llm.response` / `run.snapshot` L0 이벤트 | 사이드체인 제외, cost-state → CLI 비용 |
| ga L0 `.jsonl` | `telemetry.ledger.read_lenient` → `run.end` · `llm.response` · `peer.message.*` | `at` 이 null 이면 시간 기준 = 업로드 시각, `time_basis='ingested'` |
| Anthropic · OpenAI usage CSV/JSON | 얇은 열 매핑 어댑터 → `telemetry.usage.l0_usage(provider, u)` | 내보내기 파서는 l0-telemetry 에 없다 → baseline 요청(reports/CMD-GC0.md) |
| (나중) OTel | `telemetry.usage.l0_usage("otel", …)` | |

컨텍스트 크기는 `rlo.usage_formats.<FMT>.normalize(raw)["context"]`, 본문 토큰 추정은 `rlo` 의 `BYTES4.count` 를 쓴다. 새 파서를 만들지 않는다.

## 7. 배포 형태

- 개발: `infra/docker-compose.yml` (postgres:16, api, worker, web). 설정은 환경 변수 이름만, 값은 `.env` (저장소에는 `.env.example` 만).
- 운영(나중): 같은 이미지 3 개(api · worker · web). 시계열 부하가 커지면 TimescaleDB 하이퍼테이블로 `usage_calls` 만 바꾼다(ADR-0003).
- ga 실행기(Run 도메인, 나중): 별도 `runner` 프로세스가 ga 0.6 노드 풀을 라이브러리로 돌리고, L0 를 같은 수집 파이프라인으로 흘린다(ADR-0004).

## 8. 저장소 배치 (ADR-0002)

```
backend/app/core/                 공통: 설정 · DB · 인증 미들웨어 · 이벤트 · provenance
backend/app/api/                  FastAPI 라우터 조립(경로 → 도메인 서비스)
backend/app/domains/<domain>/     도메인 패키지 (15)
backend/app/worker/               수집 워커
backend/migrations/               SQL 마이그레이션 (docs/schema.sql 이 0001)
frontend/                         Next.js 앱
infra/                            docker-compose, CI
fixtures/                         final_task 실측(벤더링), advisor 규칙 fixture
scripts/                          check_docs.py, backtest_estimator.py, validate_openapi.py, export_work.py
docs/                             계약 문서 (변경은 contract 작업으로만)
```

경로별 담당 역할은 `docs/ownership.md`.

## 9. 관련 문서

domain-model.md · data-model.md · api-contract.md (+ api/openapi.yaml) · schema.sql · visualization.md · consulting.md · security.md · roadmap.md · ownership.md · adr/
