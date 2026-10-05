```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC19","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc19","sha":"c0138e7d484746b4b053d93379d2b0c20c62948f"}],"tests":{"passed":69,"failed":0,"skipped":1},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/tests/test_app.py::AssemblyTest.test_routes_equal_openapi_except_unbuilt_domains","backend/app/main.py","backend/app/api/wiring.py"]},{"id":"D2","state":"met","evidence":["backend/tests/test_e2e.py::EndToEndTest.test_signup_to_report_export (GC_SCHEMA_TEST_DSN, PostgreSQL 16)"]},{"id":"D3","state":"met","evidence":["backend/app/api/errors.py","backend/tests/test_app.py::AssemblyTest.test_error_bodies_are_code_message_at_top_level"]},{"id":"D4","state":"unmet","evidence":["estimation, integration, run have no router.py: their openapi paths (22) are not mounted; test_app.UNBUILT lists them and fails when one lands"]},{"id":"D5","state":"unmet","evidence":["test_e2e.test_claude_code_upload_is_ingested_and_shown_in_usage skipped here (l0-telemetry missing); ran green only against a local stub of telemetry.collect"]}]}
```

# CMD-GC19 보고: 조립된 백엔드

## 한 일
- **S1 API 시작** (`app/main.py`, `app/api/wiring.py` `wire_api()`): lifespan 에서 `DATABASE_URL` 이 있으면 풀을 열고 닫는다(없으면 경고, /healthz 만 동작). 모든 도메인 라우터(simulation 포함)를 `build_router` 로 마운트. identity·workspace 감사 recorder = `audit.api.record`, workspace 구독, `source.set_enqueuer(ingestion.api.enqueue)` + `subscribe()`, advisor·profile·notification 구독. simulation 의 `submit_proposal`(= `advisor.api.submit_proposal`)과 `usage.api.prices` 는 simulation/wiring 이 이미 import 로 연결하므로 테스트로 고정만 했다.
- **S2 워커** (`wire_worker()`, `worker/__main__.py`, `worker/README.md`): 형식 어댑터 `register_all()` (지금까지 아무도 호출하지 않아 모든 작업이 unsupported_format 이 됐을 것) + 인제스트 이벤트를 발행하는 프로세스에 필요한 구독자(advisor, profile, source, notification). workspace 구독은 API 전용. 아웃박스(프로세스 간 이벤트)·quota 경보 평가 시점·멈춘 claim 회수는 README 의 **열린 문제**로 기록(만들지 않음).
- **S3** `quota.api.list_budgets(ws)`(활성 예산 dict 목록), `report/wiring.py` 가 이를 직접 사용.
- **S4** `app/api/errors.py`: HTTPException(detail={code,message}) 을 최상위 `{code,message}` 로 풀고, 404/405/422 와 처리되지 않은 예외(500, 내용 비노출)도 같은 모양. 422 는 입력값을 되돌려 주지 않는다.
- 부수: `notification.wiring.subscribe` 를 멱등으로(라우터 import 와 조립이 둘 다 부르면 알림이 두 번 나갔을 것).

## 파일
backend/app/{main.py, api/wiring.py, api/errors.py, worker/__main__.py, worker/README.md}, domains/quota/api.py, domains/report/wiring.py, domains/notification/wiring.py, backend/tests/{test_app.py, test_e2e.py}.

## 시험 (PostgreSQL 16, GC_SCHEMA_TEST_DSN)
- `make check` 0 문제, `make test` 통과(루트 32 + backend 32(1 skip) + infra 6), 도메인 전체 `unittest discover -s app` 248 통과(5 skip). origin/claude/gracious-meitner-vp49xe 병합 후 재실행 동일.
- test_app: 라우트 = openapi(여분은 /healthz 뿐, 누락은 UNBUILT 도메인뿐), 오류 본문, 입력 비노출, 500, create_app 이 wire_api 호출·풀 열기, 구독 목록(API/워커), 어댑터 등록, 감사·enqueuer 연결, list_budgets. 변이(errors.install 제거, wire_api 제거, set_enqueuer 제거, 워커 register_all 제거, open_pool 제거, advisor 구독 제거)가 각각 실패함을 확인.
- test_e2e: signup → 개인 workspace → 출처·업로드(job_id 있음) → 워커 `run_one` → job done → usage calls·summary → advisor R2 finding(R2 fixture 를 ga_l0 형식의 시험용 어댑터로 업로드) → 예산 생성 → 리포트 생성·CSV/JSON 내보내기에 finding id 와 예산 행 → 알림·감사 로그. 오류 본문 시험은 DB 포함.
- Claude Code 업로드 시험은 `telemetry.collect` 가 없으면 skip(이 환경 skip). 로컬 스텁으로는 통과했으나 **실제 패키지로는 미검증**: 내가 만든 jsonl 형태(type/sessionId/message.usage)가 실제 `from_cc_jsonl` 입력과 맞는지 baseline 확인 필요.

## 열린 문제
1. estimation·integration·run 도메인은 router.py 가 없어 openapi 22개 경로가 마운트되지 않는다(test_app.UNBUILT).
2. report 라우터: 형식이 uuid 가 아닌 `report` id 로 내보내기를 요청하면 PostgreSQL 오류로 500(404 여야 함). 이제 {code:internal_error} 로만 응답. (report 도메인 수정 필요)
3. 워커 이벤트가 API 프로세스에 닿지 않는 문제(아웃박스), quota 경보 평가 시점, 멈춘 claim 회수는 worker/README.md.
4. e2e 는 API 와 워커를 한 프로세스에서 돌린다(버스 하나). 두 프로세스 간 전달은 검증하지 않음.

## baseline 요청
- report 도메인: 잘못된 uuid → 404(위 2).
- estimation/integration/run 라우터 항목 등록(위 1).
- 실제 l0-telemetry 로 Claude Code 업로드 시험 실행.

## 다음 세션
- 아웃박스 항목, quota.evaluate 구독, 위 라우터 항목.
