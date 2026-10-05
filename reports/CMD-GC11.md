```ga
{"schema":"report/2","from":"infra","handled":[{"id":"CMD-GC11","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc11","sha":"a03758c576e76d54767759ef4f80966633da4d1b"}],"tests":{"passed":41,"failed":0,"skipped":2},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["infra/tests/test_infra.py::ComposeTest","infra/docker-compose.yml"]},{"id":"D2","state":"met","evidence":["infra/tests/test_infra.py::EnvExampleTest",".env.example"]},{"id":"D3","state":"met","evidence":["infra/tests/test_infra.py::SecretScanTest","infra/secret_scan.py"]},{"id":"D4","state":"met","evidence":["infra/tests/test_infra.py::MakeAndCiTest","Makefile",".github/workflows/ci.yml"]}]}
```

## CMD-GC11 보고

**한 일**: dev 스택과 CI.
- `infra/docker-compose.yml`: db(postgres:16, healthcheck), api, worker, web. 값은 `.env` 에서 받는다.
- `.env.example`: 이름만(값 없음). `backend/app/core/config.py` 의 `ENV_VARS` 와 `POSTGRES_PASSWORD` 를 포함한다.
- `infra/secret_scan.py`: 비밀 패턴 grep. 값은 출력하지 않고 `경로:줄: 규칙` 만 출력한다. 패턴을 조각으로 조립해 자기 자신은 걸리지 않는다.
- `Makefile`: `db-up`, `db-down`, `migrate`, `secret-scan` 추가. `check` 가 secret-scan 을 포함하고, `test` 가 `infra/tests` 를 포함한다.
- `.github/workflows/ci.yml`: postgres:16 service 위에서 make check, make test, make secret-scan, make migrate 를 실행한다.
- `infra/README.md`, `README.md`, `infra/tests/test_infra.py`(6개 테스트) 갱신/추가.

**변경 파일**: `.env.example`, `.github/workflows/ci.yml`, `Makefile`, `README.md`, `infra/{README.md, docker-compose.yml, secret_scan.py, __init__.py, tests/}`.

**테스트**: item check(`unittest discover -s infra/tests`) 6개 통과. `make check` 통과(docs 0 problem, openapi 0 problems, secret-scan clean). `make test` 통과: 총 41개 통과, 2개 skipped. origin/claude/gracious-meitner-vp49xe 병합 후 재실행도 동일하다.

**열린 문제**
- 이 컨테이너에는 PostgreSQL 서버가 없어 `GC_SCHEMA_TEST_DSN` 스키마 테스트(2 skipped)와 `make migrate` 실행은 검증하지 못했다. CI workflow 가 실행한다.
- compose 의 api/worker/web 은 소스 마운트 방식의 dev 용이다. `python -m app.worker` 와 `app.main:create_app` 는 아직 스켈레톤이라 CMD-GC12 이후에 의미를 갖는다. web 은 frontend 구현(`next`) 이후에 동작한다.

**다음 세션 참고**: `make check` 에 secret-scan 이 들어갔으므로 테스트 픽스처에 키 모양 문자열(`ghp_…`, `sk-…`, `password = "긴문자열"`)을 쓰면 실패한다. 조각으로 조립해서 쓸 것.

**baseline 요청**: 없음.
