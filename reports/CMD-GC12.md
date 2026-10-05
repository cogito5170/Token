```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC12","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc12","sha":"94430ae194394438ec1f66ffb8fb79417a475a6b"}],"tests":{"passed":42,"failed":0,"skipped":2},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/tests/test_core.py::HealthzTest"]},{"id":"D2","state":"met","evidence":["backend/tests/test_core.py::RedactionTest"]},{"id":"D3","state":"met","evidence":["backend/tests/test_core.py::BoundaryTest.test_planted_violation_detected"]},{"id":"D4","state":"met","evidence":["backend/tests/test_core.py::EventBusTest"]}]}
```

## 한 일
- `app/core/config.py`: `Settings`/`load_settings`(환경 변수 이름만, repr 에 값 없음), `db.py`: 지연 열기 psycopg 풀, `events.py`: 동기 in-process 버스(이름 `<d>.<n>.<v>` 검사, 구독 순서 전달, 핸들러 실패 격리), `logging.py`: data-model.md 4.1 패턴 전부를 `[REDACTED:<kind>]` 로 치환하는 필터(예외 텍스트 포함).
- `app/main.py`: `create_app()` + `/healthz`; `app/api/__init__.py`: `build_router()` 가 각 도메인의 `router.py` 가 있으면 마운트.
- 테스트 `backend/tests/test_core.py` (11개 중 신규 8): healthz 200, 모든 패턴 제거, 경계 시험(임시 복사본에 교차 도메인 service import 를 심으면 검출, `api` import 는 허용), 버스 순서.

## 시험
`make check` 통과, `make test` 31 통과(2 skip: 스키마 DSN 없음), item check 11 통과. 병합 후 재실행 동일.

## 알아둘 것
- fastapi 가 없으면  는 skip 한다(다른 런타임 의존 시험과 같음).
- 컨테이너에 fastapi/psycopg 가 없어 pip 로 설치했다(pyproject 의존성 그대로). Python 3.11 에서 시험.
- `provenance.py` 는 GC0 것을 그대로 두었다. 이벤트 아웃박스(`domain_events`)와 인증 의존성(`require_member`)은 이 항목 범위 밖이라 만들지 않았다 — identity/workspace 항목에서.
- 도메인은 `app/domains/<d>/router.py` 에 `router: APIRouter` 를 두면 자동 마운트된다.
- 로그 필터는 루트 로거와 기존 핸들러에 설치한다(`create_app` 에서).

## baseline 요청
없음.
