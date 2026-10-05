```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-RN1","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/rn1","sha":"5b07d3dfde84b41167b6ed2862b10a698e36a97c"}],"tests":{"passed":14,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/app/domains/run/tests/test_gadir.py::test_expected_kinds_in_order","fixtures/monitor/recording.jsonl"]},{"id":"D2","state":"met","evidence":["test_truncated_last_line_deferred_not_lost"]},{"id":"D3","state":"met","evidence":["test_reader_never_writes","test_never_writes_in_ga_dir"]},{"id":"D4","state":"met","evidence":["SidecarTests.test_refuses_non_get","SidecarTests.test_refuses_missing_or_wrong_token"]}]}
```

# CMD-RN1 보고

## 한 일
- `gadir.py`: stdlib 전용 `.ga` 리더(`GaDirReader.poll()`, `gadir.read()`). pool.json · queue/(done, failed) · nodes/*(run, state, pi, ga-budget) · L0 jsonl · usage.json 을 `monitor-event/1` 로 변환, `observed_at` 부여, 첫 폴링은 `data.backfill=true`. jsonl 은 바이트 오프셋으로 이어 읽고 잘린 마지막 줄은 다음 폴링으로 미룬다. 파일은 읽기 전용으로만 연다. `nodes/_retired` 로 옮겨져도 같은 키로 이어 읽는다.
- `snapshot.py`: 이벤트를 접어 MonitorSnapshot(figures · tiles · edges · meters · mood)을 만든다(같은 이벤트 → 같은 스냅샷).
- 파생 mood(`derived:pace|collaboration|stall|tension|all_done`)는 값이 바뀔 때만 낸다.
- `sidecar.py`: `python3 -m app.domains.run.sidecar --ga-dir PATH`. 127.0.0.1 전용, GET 만(그 외 405), 토큰 없거나 틀리면 401(Bearer 또는 `?token=` — EventSource 용). sources · snapshot · events(SSE, Last-Event-ID, 15 s heartbeat) · recordings. 토큰은 환경변수 GC_SIDECAR_TOKEN, 없으면 생성해 준비 줄(JSON)에 한 번 출력. 녹화 파일은 `--record-dir`(`.ga` 밖)에만 쓴다.
- `replay.py` + `fixtures/monitor/script.json`(스크립트 풀) + `fixtures/monitor/recording.jsonl`(재생 결과, 38 이벤트, 테스트가 바이트 단위로 재현 확인 → CMD-DS3 입력).

## 변경 파일
backend/app/domains/run/{__init__,gadir,snapshot,sidecar,replay}.py, run/tests/{__init__,test_gadir}.py, fixtures/monitor/{script.json,recording.jsonl}.

## 테스트
make check · make test 통과, 항목 check(unittest discover run/tests) 14 통과. DB 불필요.

## 열린 문제 · 다음 세션이 알아야 할 것
- ga 0.6 의 실제 필드명은 문서에서 확정할 수 없어 관대하게 읽는다: L0 타입 키는 `type`|`kind`|`event`, ga-budget 레코드는 `tokens` · `cost_cli_microusd`(있을 때만), usage.json 은 `tokens_total` · `cost_cli_microusd` · `budget_microusd`. 실제 ga 산출물과 다르면 gadir.py 만 조정하면 된다.
- 픽스처의 `pool.live` 값 형식은 `{role,item,since,idle,children,retiring?}` 로 가정(data-model 7.1).
- 플랫폼(웹) 쪽 라우터(ga_dirs 등록 · DB)는 이 항목 범위 밖: 사이드카가 같은 GET 경로를 서빙하고, 플랫폼 라우터는 `GaDirReader` · `Snapshot` 을 재사용하면 된다.

## baseline 요청
없음.
