```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC25","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc25","sha":"b2bdf976bc24bf1a399e7a9139d2c5db3149d780"}],"tests":{"passed":327,"failed":0,"skipped":10},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/tests/test_app.py: UNBUILT = {integration}; test_routes_equal_openapi_except_unbuilt_domains, test_estimation_and_run_are_mounted, test_x_later_paths_are_not_served"]},{"id":"D2","state":"met","evidence":["estimation/tests/test_estimation_pg.py (PostgreSQL 16): test_create_get_list_roundtrip_with_workspace_evidence, test_accuracy_roundtrip_from_a_recorded_outcome, test_description_text_never_reaches_the_database (every estimation table dumped, sha256+len only)"]},{"id":"D3","state":"met","evidence":["run/tests/test_router_pg.py: test_snapshot_matches_the_reader_fold_of_the_fixture, test_sse_resumes_from_last_event_id (real uvicorn socket, fixtures/monitor), test_every_route_is_read_only_and_never_writes_inside_the_ga_dir"]},{"id":"D4","state":"met","evidence":["report/tests/test_report_router.py: test_malformed_id_is_404_with_code_and_message (abc -> 404 not_found; fails if _report_id is removed)"]}]}
```

## 한 일
- **S1 estimation**: `router.py` (GET/POST `/estimates`, GET `/estimates/{estimate}`, GET `/estimation/accuracy?from&to`), `pg_store.py` (estimator_models · estimates · estimate_evidence · estimate_outcomes), `service.py` 에 저장소 분리 · 요청 검증(enum, description ≤ 20000자) · API 모양(view) · 정확도 뷰. 읽기 = 멤버, 생성 = developer 이상, 잘못된 id/타 워크스페이스 = 404. 설명 원문은 DB 어디에도 없음(sha256 + 길이만).
- **S2 run**: `router.py` 에 `/monitor/sources` (GET 멤버, POST admin · 감사 기록에는 id 만), `/snapshot`, `/events` (SSE, Last-Event-ID 재개, 15 s heartbeat), `/recordings`, `/recordings/{recording}`. 기존 `sidecar.Monitor` / `GaDirReader` 를 그대로 사용(.ga 안에는 쓰지 않음, record_dir 없음). 소스 저장은 `ga_dirs`. x-later `/runs` 는 미구현.
- **S3 report**: 형식이 잘못된 report id → 404 `{code,message}` (router 에서 uuid 검증).
- `test_app.py`: UNBUILT = {integration}; 라우트 대 openapi 시험은 x-later 경로를 제외하고 비교하며, x-later 가 서비스되지 않는 것도 확인.

## 시험
domain 시험 265 통과 · 6 skip (`python3 -m unittest discover -s app -t .` in backend, make test 에는 포함되지 않음), `make test` 72 중 4 skip (런타임 의존성), `make check` 0 문제. 변이 확인: developer 역할 제거, 워크스페이스 조건 제거, description 원문 저장, admin 역할 제거, Last-Event-ID 무시, 디렉터리 검사 제거 모두 시험이 실패. origin/claude/gracious-meitner-vp49xe 는 6af06f5 그대로(병합할 것 없음).

## 설계 메모 / 한계
- estimates 테이블에 total_tokens 열이 없어, 저장·비교용 total 범위는 input+cache+output 각 분위수의 합으로 둔다(백테스트의 직접 total 과 다름).
- 사용자 근거는 usage.api.tasks 의 total/calls/비용만 가진다(입력·캐시·출력 분리는 전역 사전이 채움). 근거 task_ids 는 워크스페이스 작업만(estimate_evidence 가 usage_tasks FK).
- 결과(outcome) 기록은 HTTP 경로가 openapi 에 없어 `estimation.api.record_outcome(estimate_id, actual, ws, task_id)` 로만 가능. 정확도는 토큰(MAPE · P10-P90 포함률)과 list 비용(MAPE)만.
- 녹화(recording)는 실행 중인 판독기의 메모리 이벤트 로그 1 건이다(`monitor_recordings` 테이블 · 영속 저장은 쓰지 않음; 프로세스 재시작 시 사라짐). 소스 등록은 서버의 절대 경로 디렉터리만 허용(realpath, 존재 확인); 허용 루트 목록은 없다.
- 라우터 내부에 소스 저장소(MemorySources · PgSources)가 들어 있다: run 에 pg_store.py 를 둘 수 있게 되면 분리.

## baseline 요청
- run 도메인: `pg_store.py`(ga_dirs, monitor_recordings)와 wiring 소유권, 녹화 영속 저장(object store 경로) 후속 항목.
- 소스 등록 경로 허용 루트(예: GC_MONITOR_ROOTS) 정책 결정.
- 견적 outcome 을 사용 작업 라벨링 이벤트(usage task outcome)에서 자동 기록하는 후속 항목.
