```ga
{"schema":"report/2","from":"ingestion-analytics","handled":[{"id":"CMD-GC22","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc22","sha":"743a44dbe42d7fbac4dcbe59da247e5f238dea70"}],"tests":{"passed":36,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["ingestion.tests.test_ingestion.ClaimTest.test_two_workers_never_claim_one_job","ingestion.tests.test_ingestion_pg.PgIngestTest.test_two_workers_never_claim_one_job_and_pipeline_persists (PostgreSQL 16, SKIP LOCKED)"]},{"id":"D2","state":"met","evidence":["StreamTest.test_resume_after_last_event_id_has_no_gaps","RouteTest.test_sse_resume_with_last_event_id_header","PgIngestTest (replay after id 4)"]},{"id":"D3","state":"met","evidence":["FailureTest.test_failed_job_has_code_and_no_content","PgIngestTest.test_failed_job_code_only_and_notify"]}]}
```

# CMD-GC22 보고: ingestion 파이프라인과 워커

## 한 일
- `service.py`: 상태기계(queued → parsing → normalizing → loading → analyzing → done | failed), `IngestService.run_one`(claim → 형식 감지 → 파싱 → `usage.api.load_calls` → 이벤트), 3회 재시도(실패 시 queued 로 되돌리고 3회째 failed), 오류는 코드만 저장(`internal_error`, `unsupported_format`; 예외 메시지·줄·본문은 저장하지 않음). `MemoryStore`(테스트).
- `pg_store.py`: claim 은 `UPDATE … WHERE id=(SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)` 한 문장. 이벤트 행(seq 는 작업 행 잠금으로 직렬화)은 상태 변경과 같은 트랜잭션에서 쓰고 `pg_notify('ingest_job_<id>')`. `wait` 는 LISTEN, 실패하면 폴링.
- SSE `stream()`: `Last-Event-ID` 이후를 DB 에서 재생 후 실시간 추적, 15초 heartbeat, done/failed 뒤 닫음. 라우터: `GET /v1/workspaces/{ws}/ingest-jobs`, `/{job}`, `/{job}/events` (require_member, 다른 워크스페이스는 404).
- 거부 행: `ingest_rejects(line_no, error_code)` 만(원문 없음). load 단계의 `unknown_model` 도 줄 번호로 기록.
- `registry.py`: 형식 어댑터 등록(`register`, `ParsedCall/Reject/Session/Task`). 실제 어댑터는 CMD-GC23.
- `api.enqueue(upload_id) -> job_id`(source 의 `Upload.job_id` 훅, 같은 업로드의 진행 중 작업은 재사용). `worker/__main__.py`: `python -m app.worker`.
- 발행: `ingestion.job.progressed`, `.finished`(upload_id 포함), `.failed`.

## 바뀐 파일
`backend/app/domains/ingestion/**`, `backend/app/worker/__main__.py`, `reports/CMD-GC22.md`.

## 테스트
ingestion 21건 통과(메모리 18 + PostgreSQL 16 실DB 3 + 라우트; 의존성/DSN 없으면 skip). `make check` 통과. `make test` 는 병합 후 통과(경계 규칙 위반 없음: 타 도메인은 `usage.api` 만). origin/claude/gracious-meitner-vp49xe 병합 후 재실행.

## 알아둘 점 (다음 세션)
- 어댑터는 `registry.register(adapter)` (`kind`, `parser`, `detect(filename, head)`, `parse(f)`). 파일 이름은 source.api 로 얻을 수 없어 `detect` 에 빈 문자열을 넘긴다. `declared_format` 이 있으면 그것을 우선.
- 이벤트 stage: queued(재시도 포함) · parsing 10 · normalizing 40 · loading 70 · analyzing 90 · done 100 · failed.
- `load_calls` 는 한 번에 호출(전부 메모리). 매우 큰 파일은 청크 적재가 필요할 수 있다.

## 후속 수정 (baseline 지적: uploads 직접 조회)
- `ingestion/pg_store.py` 의 `uploads` SQL 조회 제거. `source.api.get_upload(upload_id)`(workspace_id, source_id, declared_format, filename; 없거나 파기되면 404)를 추가하고 `IngestService` 가 그것을 쓴다(`enqueue` 의 workspace, 파이프라인의 source_id · declared_format · filename).
- source 쪽 변경: `source/service.py`(get_upload), `source/api.py`, `source/wiring.py`(`set_enqueuer` 가 없으면 `ingestion.api.enqueue` 를 지연 import 하는 기본 enqueuer; `subscribe()` 는 router import 시 이미 호출됨). 테스트: `GetUploadTest`, `WiringTest`.
- 경계 테스트 `ingestion.tests.test_ingestion.BoundaryTest`: ingestion 소스에 `FROM/JOIN/INTO/UPDATE uploads|sources|usage_*|workspaces|users` 가 있으면 실패.
- 테스트: ingestion 22건 + source 14건 통과(PostgreSQL 16 포함).

## baseline 요청 (남은 것)
1. 요청 3(워커 프로세스의 `ingestion.job.finished` 가 api 프로세스에 닿는 경로 · 아웃박스)과 요청 4(parsing 에 멈춘 claim 회수)는 baseline 이 이후 항목으로 기록한다.
