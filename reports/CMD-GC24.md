```ga
{"schema":"report/2","from":"ingestion-analytics","handled":[{"id":"CMD-GC24","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc24","sha":"61595b5575a8958822902b2dce4f47a6ee86a961"}],"tests":{"passed":57,"failed":0,"skipped":28},"change_size":"interface","items":[{"id":"D1","state":"met","evidence":["tests/contract/test_contract.py::test_migrations_in_order_equal_schema; 0001+0002 applied to empty PostgreSQL 16 (local), usage_tasks.user_id present"]},{"id":"D2","state":"met","evidence":["ingestion/tests/adapters/test_usage_extras.py: exact sha256 prefix/block hashes, stable across parses, no body in repr, NULL (not ''/[]) without body, ga run.end NULL"]},{"id":"D3","state":"unmet","evidence":["CSV-row NULL test skips here (needs real l0-telemetry); exports.py never sets the fields so they default to None"]},{"id":"D4","state":"met","evidence":["usage/tests/test_usage_extras.py::test_prices_final_task_with_version, test_prices_use_newest_version"]},{"id":"D5","state":"met","evidence":["backend/tests/test_ingest_to_advisor.py: R2 fires on ingested fixture via advisor.api; silent without hashes; advisor R2/R3/R4 fixtures unchanged and green"]}]}
```

## 한 일
- **S1 계약**: `prompt_prefix_hash`, `content_hashes`(usage_calls), `first_try_success`(usage_tasks)는 0001 에 이미 있었다. 새로 필요한 것은 `usage_tasks.user_id`(uuid, users FK, ON DELETE SET NULL, 부분 인덱스)뿐이라 `0002_usage_extras.sql` 로 추가. `docs/schema.sql` = 0001 + 0002 바이트 연결. `docs/data-model.md` 갱신(해시 정의, user_id).
- **S2 어댑터**: `common.content_digest` 가 본문을 해시한 뒤 `drop_bodies` 가 본문을 버린다. `prompt_prefix_hash` = 고정 앞부분(`system`, 없으면 첫 블록) 최대 4 KiB 의 SHA-256 hex 64자. `content_hashes` = 블록마다 `<sha256 앞 12 hex>:<tokens>`(R2 가 tokens 를 필요로 함; 파서가 블록 `tokens` 를 주면 그 값, 아니면 ceil(UTF-8 바이트/4) 추정). Claude Code, ga L0 `llm.response` 에 적용. ga `run.end` 와 CSV 는 NULL.
- **S3 usage**: TaskIn/TaskRow 에 `first_try_success`, `user_id`; calls 응답에 `prompt_prefix_hash`, `content_hashes`, `cost_list_nanousd`; tasks 응답에 `first_try_success`, `user_id`; `usage.api.prices()` -> {model:{in,out,cr,cw5,cw1,version}} (모델별 최신 버전).

## 변경 파일
backend/migrations/{0002_usage_extras.sql,README.md}, docs/{schema.sql,data-model.md}, tests/contract/test_contract.py, backend/app/domains/ingestion/adapters/{common,claude_code,ga_l0}.py, backend/app/domains/usage/{api,service,pg_store}.py, 시험 3개(ingestion/tests/adapters/test_usage_extras.py, usage/tests/test_usage_extras.py, backend/tests/test_ingest_to_advisor.py).

## 시험
make check, make test green (GC_SCHEMA_TEST_DSN=로컬 PostgreSQL 16). 도메인 시험(`unittest discover -s app`): 신규 포함 통과; fastapi/psycopg 없음으로 app.api 임포트와 PG 시험은 skip/기존 오류. 변경 규칙(R2) 시험: 해시가 없으면 침묵, 있으면 발화.

## 열린 문제
- 실제 l0-telemetry 이벤트의 본문 키(`system`, `messages`, `prompt`, `content`)는 가정이다(파서가 이 환경에 없음). baseline 이 실제 패키지로 돌려 확인 요청.
- PgStore 의 새 SQL(user_id 삽입, TASK_COLS)은 psycopg 가 없어 실행 검증 못 함.
- tokens 추정(바이트/4)은 근사값. 파서가 블록 토큰을 주면 자동으로 그 값을 쓴다.

## baseline 요청
1. `tests/contract/test_contract.py` 를 수정했다(0001 == schema 였던 검사를 "모든 마이그레이션 연결 == schema.sql" 로). 계약 파일 소유권 범위 안인지 확인 요청.
2. 교차 도메인 e2e 시험은 경계 검사 때문에 `backend/tests/` 에 두었다.
3. 새 키(`cost_list_nanousd`, 해시, `first_try_success`, `user_id`)를 OpenAPI 응답 스키마에 추가할지 결정 요청(라우터/openapi 는 내 범위 밖).
4. 인제스트가 `TaskIn.user_id` 를 채우는 곳(업로더) 연결은 ingestion service 몫.

## 다음 세션
- 실제 패키지로 어댑터 시험(CSV NULL 포함) 실행, advisor R3 e2e 추가.
