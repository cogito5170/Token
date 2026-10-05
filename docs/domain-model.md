# 도메인 모델

각 도메인 = `backend/app/domains/<id>/` 패키지 하나. 형식은 고정이다(`scripts/check_docs.py` 가 읽는다).

- `owned_tables:` 줄의 테이블은 `docs/schema.sql` 에 있어야 하고, 한 테이블은 정확히 한 도메인에만 나온다.
- 공개 인터페이스는 `app/domains/<id>/api.py` 의 함수만이다. 다른 도메인은 `service.py` · `repo.py` 를 import 하지 않는다.
- 이벤트 이름은 `<domain>.<noun>.<verb-past>`. 페이로드는 id 와 범위(workspace_id, 기간)만 담고 본문 · 키는 담지 않는다.

공통 금지(모든 도메인): 공급자 키 · 비밀번호 · 토큰 원문을 로그 · 이벤트 · 응답에 넣지 않는다. 다른 도메인 테이블에 쓰지 않는다. MEASURED 값을 덮어쓰지 않는다.

---

## `identity` — Identity

- 책임: 계정 생성, 로그인, 액세스 토큰(JWT, 15 분) 발급, 리프레시 토큰(30 일, 회전) 관리, Argon2id 비밀번호 해시.
- owned_tables: `users`, `refresh_tokens`
- 공개 인터페이스: `current_user(request) -> User`, `get_user(user_id) -> User`, `require_user` (FastAPI 의존성).
- 발행 이벤트: `identity.user.created`, `identity.session.revoked`
- 구독 이벤트: 없음
- 하지 않는 것: 워크스페이스 권한 판단(그것은 workspace), 비밀번호 · 리프레시 토큰 원문 저장(해시만), 토큰을 URL 에 싣기.

## `workspace` — Workspace

- 책임: 워크스페이스 · 구성원 · 역할(admin · developer · viewer) · 프로젝트. 모든 데이터 접근의 범위 검사(`ws` 경로 인자).
- owned_tables: `workspaces`, `workspace_members`, `projects`
- 공개 인터페이스: `require_member(ws_id, user, min_role)`, `get_workspace(ws_id)`, `list_projects(ws_id)`.
- 발행 이벤트: `workspace.workspace.created`, `workspace.member.changed`, `workspace.project.created`
- 구독 이벤트: `identity.user.created` (개인 워크스페이스 자동 생성)
- 하지 않는 것: 사용 데이터 읽기 · 쓰기, 세분화된 프로젝트 권한(나중).

## `source` — Source

- 책임: 기록 출처 등록(업로드 · 나중의 공급자 연결), 업로드 파일 메타데이터(크기, sha256, 감지 형식, 저장 경로). 원본 파일은 객체 저장소에 두고 보존 기간 뒤 지운다.
- owned_tables: `sources`, `uploads`
- 공개 인터페이스: `create_upload(ws_id, source_id, file) -> Upload`, `open_upload(upload_id) -> BinaryIO`, `get_source(source_id)`.
- 발행 이벤트: `source.upload.stored`
- 구독 이벤트: `ingestion.job.finished` (보존 정책에 따라 원본 삭제 예약)
- 하지 않는 것: 파일 내용 파싱(ingestion), 원본 본문을 DB 에 저장.

## `ingestion` — Ingestion

- 책임: 수집 작업 상태기계(queued → parsing → normalizing → loading → analyzing → done | failed), 형식 감지, 기존 파서 호출(l0-telemetry · rlo), 비밀값 제거, `UsageCall` 정규화, 중복 제거 키 계산, 진행 이벤트(SSE 원천), 거부 행 기록.
- owned_tables: `ingest_jobs`, `ingest_job_events`, `ingest_rejects`
- 공개 인터페이스: `enqueue(upload_id) -> Job`, `get_job(job_id)`, `stream_events(job_id, after_seq)` (SSE), `claim_next()` (worker 전용).
- 발행 이벤트: `ingestion.job.progressed`, `ingestion.job.finished`, `ingestion.job.failed`
- 구독 이벤트: `source.upload.stored` (자동 enqueue)
- 하지 않는 것: usage 테이블에 직접 쓰기(→ `usage.api.load_calls`), 새 공급자 파서 작성(재사용만; 없는 것은 baseline 요청), 프롬프트 본문 저장(사용자가 켠 경우에만 해시 외 보관).

## `usage` — Usage

- 책임: 정규화 사용 모델의 저장과 읽기. 호출 · 세션 · 작업 · 모델 카탈로그 · 정가표 · 일별 집계. 비용 계산(정가 환산, CALCULATED). 차트용 시계열 · 분포 · 비교 쿼리.
- owned_tables: `models`, `model_prices`, `usage_sessions`, `usage_tasks`, `usage_calls`, `usage_daily`
- 공개 인터페이스: `load_calls(job_id, calls: list[UsageCall]) -> LoadResult`, `price_call(call) -> int`, `summary(ws, period)`, `token_series(ws, period, bucket, group_by)`, `call_size_histogram(ws, period, bins)`, `compare(ws, dims, period)`, `calls(ws, filter)`, `tasks(ws, filter)`.
- 발행 이벤트: `usage.calls.ingested`, `usage.task.outcome_set`
- 구독 이벤트: 없음 (ingestion 이 인터페이스로 부른다)
- 하지 않는 것: 예산 판단(quota), 낭비 판단(advisor), MEASURED 토큰 · CLI 비용 수정, 화면 모양 결정.

## `quota` — Quota

- 책임: 예산(작업 · 일 · 월 · 워크스페이스/프로젝트 범위, 기준 `list` | `cli`), 두 기준 사용률, 소진 예측(선형 + 구간), 임계(50 · 80 · 100 %) 경보 생성.
- owned_tables: `budgets`, `budget_alerts`
- 공개 인터페이스: `burn(budget_id) -> BurnSeries`, `check(ws, scope, extra_cost) -> BudgetVerdict` (Proposal 적용 전 예산 검사), `list_alerts(ws)`.
- 발행 이벤트: `quota.alert.raised`
- 구독 이벤트: `usage.calls.ingested`
- 하지 않는 것: 실행 정지 자체(나중 run 이 verdict 를 따른다), 비용 재계산(usage 값만 읽는다).

## `estimation` — Estimation

- 책임: 실행 전 견적. 입력 특징화, 근거 집합(유사 과거 작업 N 건) 선택, P10/P50/P90(토큰 입력 · 캐시 · 출력, 비용 두 기준, 호출 수, 시간)과 성공 확률, 실제값과 비교한 오차(MAPE) 기록. 전역 사전(FINAL_TASK)과 사용자별 보정.
- owned_tables: `estimates`, `estimate_evidence`, `estimate_outcomes`, `estimator_models`
- 공개 인터페이스: `estimate(ws, request) -> Estimate`, `accuracy(ws, period) -> Accuracy`, `refit(scope)`.
- 발행 이벤트: `estimation.estimate.created`, `estimation.outcome.recorded`
- 구독 이벤트: `usage.task.outcome_set` (견적과 연결된 작업이면 오차 기록), `usage.calls.ingested` (재적합 예약)
- 하지 않는 것: 추정값을 MEASURED 로 표시, 근거 없이 점 하나만 내기.

## `advisor` — Advisor

- 책임: 낭비 규칙 7 종(consulting.md 3 절) 실행 → 발견(finding, 근거 호출 id 와 절감 추정) → Proposal 생성. Proposal 의 상태기계(proposed → accepted/rejected → applied | expired)와 결정 기록. 다른 출처(simulation, 나중 run 노드)의 Proposal 도 이 인터페이스로만 들어온다.
- owned_tables: `advisor_rules`, `advisor_findings`, `proposals`, `proposal_decisions`
- 공개 인터페이스: `run_rules(ws, period) -> list[Finding]`, `submit_proposal(ws, origin, change, evidence) -> Proposal`, `decide(proposal_id, user, decision)`, `apply(proposal_id)` (정책 → `quota.check` → 사용자 확인 뒤에만), `list_findings(ws)`.
- 발행 이벤트: `advisor.finding.created`, `advisor.proposal.created`, `advisor.proposal.decided`, `advisor.proposal.applied`
- 구독 이벤트: `usage.calls.ingested`
- 하지 않는 것: 사용자 확인 없이 설정 · 예산 · 저장소 변경, 절감액을 MEASURED 로 표시, LLM 으로 규칙 판정(규칙은 결정적 코드).

## `simulation` — Simulation

- 책임: What-if. 가정(모델 교체, 문맥 상한, 노드 수, 캐시 고정)을 받아 과거 호출을 다시 계산하고 범위로 돌려준다. 모든 결과에 가정 목록과 데이터 기준(기간, 호출 수, 가격표 버전)을 저장.
- owned_tables: `simulations`
- 공개 인터페이스: `simulate(ws, assumptions, basis) -> Simulation`, `get(sim_id)`, `to_proposal(sim_id)` (→ `advisor.submit_proposal`).
- 발행 이벤트: `simulation.simulation.completed`
- 구독 이벤트: 없음
- 하지 않는 것: 가정 없이 결과 저장, 결과를 MEASURED/ESTIMATED 로 표시(항상 SIMULATED).

## `profile` — Profile

- 책임: 개인 프로필(예산, 품질 하한, 선호 모델 · 공급자, 과금 방식, 팀 규모), 사용자별 통계(작업 종류 × 모델 × 구조별 맞힌 작업당 토큰 · 성공률 = 개인 라우터 · 견적 통계), 맞춤 추천.
- owned_tables: `profiles`, `personal_stats`, `recommendations`
- 공개 인터페이스: `get_profile(user, ws)`, `update_profile(...)`, `stats(user, ws) -> PersonalStats`, `recommendations(user, ws)`.
- 발행 이벤트: `profile.profile.updated`, `profile.recommendation.created`
- 구독 이벤트: `usage.calls.ingested`, `usage.task.outcome_set`
- 하지 않는 것: 다른 사용자 통계 노출, 추천을 자동 적용(추천 → Proposal → 확인).

## `report` — Report

- 책임: 기간 리포트(사용량 · 절감액 · 다음 기간 권장 설정) 생성과 내보내기(JSON · CSV; PDF 는 나중).
- owned_tables: `reports`
- 공개 인터페이스: `generate(ws, period) -> Report`, `export(report_id, fmt) -> bytes`.
- 발행 이벤트: `report.report.generated`
- 구독 이벤트: 없음 (나중: 주간 스케줄)
- 하지 않는 것: 원본 호출 테이블을 직접 집계(usage · advisor · quota 인터페이스만 사용).

## `notification` — Notification

- 책임: 앱 내 알림 저장 · 읽음 처리, 채널 설정(앱 내 · 이메일; Slack 은 나중).
- owned_tables: `notifications`, `notification_prefs`
- 공개 인터페이스: `notify(user|ws, kind, ref, text)`, `list(user)`, `mark_read(id)`.
- 발행 이벤트: 없음
- 구독 이벤트: `quota.alert.raised`, `ingestion.job.finished`, `ingestion.job.failed`, `advisor.proposal.created`
- 하지 않는 것: 알림 본문에 키 · 프롬프트 본문 싣기.

## `audit` — Audit

- 책임: 추가 전용 감사 로그. 누가 · 언제 · 무엇을(로그인, 업로드, Proposal 결정 · 적용, 예산 변경, 키 등록 · 삭제, (나중) 실행 시작 · 정지).
- owned_tables: `audit_log`
- 공개 인터페이스: `record(actor, action, target, detail)`, `query(ws, filter)`.
- 발행 이벤트: 없음
- 구독 이벤트: 없음 (각 도메인이 `record` 를 직접 부른다)
- 하지 않는 것: 행 수정 · 삭제(DB 권한과 트리거로 막는다), 다른 도메인 호출, detail 에 비밀값 저장.

## `integration` — Integration

- 책임: 외부 연동(GitHub · Slack, 나중) 설정, 공급자 키 봉투 암호화 보관(ADR-0007). 키는 지문(fingerprint)과 끝 4 자만 돌려준다.
- owned_tables: `integrations`, `provider_credentials`
- 공개 인터페이스: `store_credential(ws, provider, secret) -> CredentialRef`, `use_credential(ref) -> ContextManager[str]` (메모리 안에서만), `revoke_credential(ref)`.
- 발행 이벤트: `integration.credential.stored`, `integration.credential.revoked`
- 구독 이벤트: 없음
- 하지 않는 것: 키 원문을 응답 · 로그 · 이벤트 · 예외 메시지에 넣기, 키를 디스크에 평문으로 쓰기.

## `run` — Run (모니터 1b, 실행 나중)

- 책임: (1b) **라이브 모니터의 읽기 모델.**
  - 등록된 로컬 `.ga` 디렉터리를 읽기만 한다: `pool.json`, `queue/`, `nodes/*/run.json` · `state.json` · `pi.json` · `ga-budget.jsonl`, L0 `*.jsonl`, `usage.json`.
  - 읽은 것을 `monitor-event/1` 로 바꾸고, 관측 시각을 찍고, 스냅샷 · SSE · 녹화로 낸다(data-model.md 7 절).
  - 같은 리더가 데스크톱 셸의 로컬 사이드카로도 돈다(ADR-0008).
  - (나중) 플랫폼 안 ga 0.6 실행, 노드 타임라인 · 동료 네트워크 · 판정 · 작업 흐름.
- owned_tables: `ga_dirs`, `monitor_recordings`, `runs`, `run_nodes`, `run_events`, `run_messages`, `run_verdicts`
- 공개 인터페이스:
  - (1b) `snapshot(source_id) -> MonitorSnapshot`, `stream(source_id, after_seq)` (SSE), `record(source_id)`, `recording(rec_id)`.
  - `gadir.read(path) -> Iterator[MonitorEvent]` (stdlib 만 쓰는 순수 리더).
  - (나중) `start(ws, plan)` (승인 게이트 · 예산 검사 뒤), `stop`, `timeline`, `network`, `verdicts`, `flow`.
- 발행 이벤트: `run.monitor.recorded`, (나중) `run.run.started`, `run.run.finished`, `run.node.proposed`
- 구독 이벤트: (나중) `quota.alert.raised` (상한에서 체크포인트 후 정지)
- 하지 않는 것:
  - `.ga` 안의 어떤 파일도 쓰지 않는다. 열기는 읽기 전용이고 잠그지도 않는다.
  - 노드를 멈추거나 바꾸는 조작을 하지 않는다. 조작은 나중이며 승인 게이트 뒤에 온다.
  - ga-sdk 코드를 수정 · 복사하지 않는다.
  - 노드 제안을 바로 적용하지 않는다(→ `advisor.submit_proposal`).
  - 사용자 확인 없이 push · 의존성 변경을 하지 않는다.
