```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC10","rev_seen":1,"status":"done"}],"commits":[],"tests":{"passed":36,"failed":0,"skipped":0},"change_size":"interface","items":[{"id":"D1","state":"met","evidence":["backend/migrations/0001_init.sql == docs/schema.sql (tests/contract MigrationFileTest)"]},{"id":"D2","state":"met","evidence":["MigrationApplyTest applies all migrations to an empty DB (ran against local PostgreSQL 16; skips only without GC_SCHEMA_TEST_DSN)"]},{"id":"D3","state":"met","evidence":["NoSecretInResponsesTest walks every response $ref; planted-secret detector test"]},{"id":"D4","state":"met","evidence":["make check: check_docs 0 problems, openapi 0 problems"]}]}
```

## 한 일
- `backend/migrations/0001_init.sql` 을 `docs/schema.sql` 과 바이트 동일하게 생성.
- `tests/contract/test_contract.py`: 마이그레이션 동일성, 번호 연속성, 빈 DB 적용(GC_SCHEMA_TEST_DSN 없으면 skip), 모든 응답 스키마($ref 재귀)에 비밀 필드(password/secret/api_key/private_key/ciphertext/refresh_token 등) 없음 + 심은 비밀을 잡는 탐지기 테스트.
- 허용 예외: `TokenPair.access_token`(인증 응답).

## 테스트
`make check`, `make test`, 항목 check(unittest tests/contract) 모두 통과 (PostgreSQL 16 로컬 사용).

## 다음 세션 참고
- 이후 계약 변경은 `NNNN_<name>.sql` 추가 + `docs/schema.sql` 갱신. 현재 테스트는 `0001` 만 schema.sql 과 동일성을 요구한다(0002 이후 추가 시 test 의 동일성 검사를 "마이그레이션 누적 == schema.sql" 로 확장해야 함 — baseline 요청: 해당 계약 항목에서 처리).
- 요청: `tests/test_schema.py` 와 일부 중복이나 `tests/**` 는 계약 소유라 건드리지 않음.
