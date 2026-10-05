```ga
{"schema":"report/2","from":"ingestion-analytics","handled":[{"id":"CMD-GC20","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc20","sha":"bbaa2be39b3e738ae8cc854b016572c84161c48a"}],"tests":{"passed":10,"failed":0,"skipped":2},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["test_over_limit_is_413_and_leaves_nothing","test_declared_size_over_limit_is_413_without_reading"]},{"id":"D2","state":"met","evidence":["test_stores_sha256_size_path_and_purge_after"]},{"id":"D3","state":"met","evidence":["test_event_carries_ids_only"]}]}
```

## 한 일
`source` 도메인 구현: 출처(sources) 등록·목록, 업로드(multipart, 청크 스트리밍, sha256·크기 기록, 객체 저장소 키 `<ws>/<upload_id>`, `purge_after` = 7일), `source.upload.stored` 이벤트(ids만: workspace_id, source_id, upload_id). `GC_UPLOAD_MAX_BYTES` 초과 시 413(부분 객체 삭제). 파일명은 basename 으로 정리. `ingestion.job.finished` 구독으로 purge 시계 재시작(payload 에 upload_id 가 있을 때만).

## 파일 (모두 backend/app/domains/source/)
service.py, pg_store.py, wiring.py, api.py (create_upload / open_upload / get_source), router.py, _identity.py, tests/test_source.py

## 테스트
도메인 unittest 12건: 통과 10, 실패 0, 건너뜀 2 (fastapi·python-multipart 없는 환경에서 HTTP 테스트 skip — 라우터는 컴파일만 확인, 이 컨테이너에서 실행되지 않음). make check, make test 통과(스키마 DB 테스트는 DSN 없어 건너뜀).

## 열린 문제 / baseline 요청
- `Upload.job_id` 는 openapi 에서 required 이나 source 는 job 을 모른다. `wiring.set_enqueuer(fn)` 훅을 두었고, 미설정이면 job_id 는 null. GC22(ingestion)가 `set_enqueuer(ingestion.enqueue)` 를 연결하거나, 계약을 nullable 로 바꿔야 한다.
- `_identity.py` 는 workspace 와 같은 폴백(identity.api 부재). identity.api 가 current_user 를 내보내면 제거.
- main.py 라우터 등록(`build_router`)에 source router 포함은 core-backend 몫(요청).
- 라우터는 fastapi 가 스풀링한 뒤 청크를 읽는다. Content-Length 가 한도+64KiB 를 넘으면 읽기 전에 413.

## 다음 세션
GC22 는 `source.api.open_upload(upload_id)` 를 쓴다(없거나 purge 됐으면 404). purge 실행기(purged_at 설정, 객체 삭제)는 이 항목 범위 밖.
