```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC18","rev_seen":2,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc18","sha":"93fa46c71101e4267329dac8ab4f947fdbe8e165"}],"tests":{"passed":342,"failed":0,"skipped":6},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/app/domains/integration/tests/test_integration_pg.py::test_store_list_revoke_never_exposes_the_key (pg_dump --data-only scan: key, key minus last4, hex, base64)","test_integration.py::EnvelopeTest.test_roundtrip_and_row_holds_no_plaintext"]},{"id":"D2","state":"met","evidence":["test_integration_pg.py::test_store_list_revoke_never_exposes_the_key (all responses+headers, root log capture at DEBUG, audit-log detail == ids)","test_integration_pg.py::test_key_in_a_wrong_field_is_refused_and_not_echoed","test_integration.py::LifecycleTest.test_no_log_record_or_error_contains_the_key","test_integration.py::LifecycleTest.test_audit_and_events_carry_ids_only"]},{"id":"D3","state":"met","evidence":["test_integration_pg.py::test_wrong_kek_fails_decryption_and_right_kek_reads","test_integration.py::EnvelopeTest.test_wrong_kek_fails_decryption","test_integration.py::EnvelopeTest.test_ciphertext_is_bound_to_its_row","test_integration.py::EnvelopeTest.test_ciphertext_copied_to_another_row_of_same_workspace_and_provider_fails","test_integration_pg.py::test_ciphertext_copied_to_another_row_does_not_open"]},{"id":"D4","state":"met","evidence":["test_integration_pg.py::test_store_list_revoke_never_exposes_the_key (row lengths 0|0|0, revoked_at set)","test_integration.py::LifecycleTest.test_revoke_wipes_ciphertext_and_blocks_use"]},{"id":"D5","state":"met","evidence":["test_integration_pg.py::test_non_admins_cannot_store_or_revoke (developer/viewer 403, outsider 404, members list 200)"]},{"id":"D6","state":"met","evidence":["backend/tests/test_app.py UNBUILT = {estimation, run}","test_integration_pg.py::test_routes_equal_openapi_for_integration"]},{"id":"D7","state":"met","evidence":["backend/app/domains/integration/crypto.py (cryptography AESGCM + HKDF, KEK from GC_KEK_<GC_KEK_ID>)","test_integration.py::EnvelopeTest.test_fresh_dek_and_nonce_per_credential, test_dek_is_wrapped_by_the_kek, test_missing_or_bad_kek_refuses_to_store, test_kek_rotation_keeps_old_rows_readable"]},{"id":"D8","state":"met","evidence":["GET /integrations is a read-only list of the integrations table; no connect/create route exists in openapi (stated in integration/__init__.py)"]}]}
```

# CMD-GC18 보고: integration 도메인 — 공급자 키 보관

## 한 일
- **경로 3개** (`integration/router.py`): `GET /v1/workspaces/{ws}/integrations`(멤버), `GET|POST /{ws}/provider-credentials`(목록은 멤버, 저장은 admin), `DELETE /{ws}/provider-credentials/{credential}`(admin). 비멤버는 `require_member` 대로 404, 역할 부족은 403.
- **봉투 암호화** (`crypto.py`, `cryptography` 의 AES-GCM·HKDF 만 사용, 직접 만든 암호 없음): 키마다 무작위 256-bit DEK 로 AES-256-GCM(96-bit nonce). DEK 는 KEK 로 AES-GCM 래핑, `wrapped_dek` = 래핑 nonce ‖ 암호문. AAD 가 `workspace_id|credential_id|provider` 를 묶어 암호문을 다른 행으로 옮기면 복호화가 실패한다. KEK id 는 `GC_KEK_ID`, 재료는 `GC_KEK_<id>`(base64 32 바이트)에서만 온다. 행의 `kek_id` 로 복호화하므로 KEK 회전 뒤에도 옛 행을 읽는다. KEK 가 없거나 형식이 틀리면 503 `key_unavailable`, 아무것도 저장하지 않는다.
- **API 응답**: `CredentialRef {id, provider, fingerprint, last4, created_at, revoked_at}` 만(openapi 그대로). `fingerprint` = KEK 에서 HKDF 로 파생한 키의 HMAC-SHA256(워크스페이스 범위). 같은 워크스페이스에 같은 키가 활성 상태로 있으면 409.
- **입력 검사**: POST 본문은 pydantic 모델이 아니라 raw JSON 객체로 받아 서비스가 직접 검사한다. `provider`·`secret` 이외의 필드, enum 밖의 provider 는 422. 오류 메시지는 고정 문구라 입력값도 필드 이름도 되돌려 주지 않는다(키를 필드 이름에 넣어도 echo 되지 않음). secret 은 앞뒤 공백 제거 뒤 16–4096 자, 공백·제어 문자 없음.
- **삭제**: `revoked_at` 설정과 같은 UPDATE 에서 `ciphertext`·`nonce`·`wrapped_dek` 를 빈 값으로 지운다(crypto-shredding). 감사 로그가 가리키는 참조 행은 남고, 목록에 `revoked_at` 으로 보인다. 다시 지우면 404.
- **감사·이벤트·로그**: `credential.store`/`credential.revoke`, detail = `{workspace_id, credential_id}`, target_kind `provider_credential`. 이벤트 `integration.credential.stored|revoked` 도 같은 id 만. 로그는 id 만. `CredentialRow.__repr__` 는 암호문 바이트를 출력하지 않는다.
- **`integration.api`**: `store_credential`, `use_credential(ws, id)`(컨텍스트 안에서만 평문), `revoke_credential`.
- **스텁**: `GET /integrations` 는 `integrations` 테이블을 읽기만 한다. 연결·생성 경로는 계약에 없으므로 지금은 항상 빈 목록이다.

## 시험 (PostgreSQL 16.14, GC_SCHEMA_TEST_DSN)
- `make check` 0 문제(secret_scan 깨끗함: 시험 키는 런타임에 `gc-test-fake.<hex>`, KEK 는 `os.urandom`). `make test` 루트 32 + backend 32(1 skip) + infra 6 통과. 도메인 전체 `unittest discover -s app` 276 통과(5 skip), 그중 integration 28(단위 22 + PG/HTTP 6). 합계 통과 340, skip 6, 실패 0. origin/claude/gracious-meitner-vp49xe 는 이미 반영돼 있었다(Already up to date). 병합 시점에 검사를 다시 돌려 같은 결과를 확인했다.
- 시험 키는 일부러 로그 redactor 와 audit 의 secret 패턴에 걸리지 않는 모양으로 만들었다. 그래서 누출을 필터가 가리지 못하고 시험이 직접 잡는다. 수동 변이(secret 을 로그에 넣기, 감사 detail 에 키 앞부분 넣기)는 각각 3 개 시험을 실패시켰다.
- 런타임 의존성(cryptography, fastapi, psycopg, pg_dump/psql, DSN)이 없으면 skip 하고 오류를 내지 않는다.

## rev 2 (baseline 반려 M2)
- 같은 워크스페이스 · 같은 provider 의 두 자격 증명에서 1 행의 ciphertext/nonce/wrapped_dek/kek_id 를 2 행에 복사하면 `use_credential(2 행)` 이 decrypt_failed(HTTP 500)로 실패하는 시험을 추가했다(단위 + PG). AAD 에서 credential id 를 빼는 변이(M2)는 이제 두 시험을 실패시킨다. 도메인 278 통과(5 skip), 합계 342 통과. 지시대로 통합 브랜치는 병합하지 않았다.

## 지시와 다른 점
- 지시에 있던 `label`·`last_used_at` 은 openapi `CredentialRef`/`CredentialCreate` 와 schema.sql 에 없다. 그래서 만들지 않았고 응답은 계약 그대로다. 필요하면 contract 작업으로 넣어야 한다.
- fingerprint 는 현재 KEK 에서 파생한다. KEK 를 회전하면 회전 전 키와의 중복 감지(409)가 되지 않는다. 회전 시 fingerprint 를 다시 계산하는 작업을 roadmap 에 넣어야 한다.

## baseline 요청 (내 범위 밖)
1. `backend/app/core/config.py`: `GC_KEK_<id>` 는 이름이 패턴이라 `SECRET_ENV_VARS` 에 없다. 설정 덤프 제외 규칙에 접두어를 추가해 달라. 정확한 줄: `SECRET_ENV_PREFIXES = ("GC_KEK_",)  # GC_KEK_ID itself is not secret; GC_KEK_<id> is`
2. `.env.example`: KEK 재료 줄 추가. 정확한 줄: `GC_KEK_dev=            # base64 of 32 random bytes: python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`
3. `backend/tests/test_e2e.py::reset_singletons` 목록에 `"integration.wiring"` 추가(같은 프로세스에서 다른 DB 풀을 붙잡지 않도록).
4. 도메인 시험(`backend/app/domains/*/tests`)이 `make test` 에 포함되지 않는다. 정확한 줄: `	cd backend && $(PY) -m unittest discover -s app -t .`
5. 운영 KMS 키링은 만들지 않았다(`EnvKeyring` 과 같은 메서드 `current_id()`·`kek(id)` 를 구현하면 된다).
