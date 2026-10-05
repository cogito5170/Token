```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC15","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc15","sha":"SHAPLACEHOLDER"}],"tests":{"passed":83,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backend/app/domains/audit/tests/test_audit.py::PgAppendOnlyTest (UPDATE/DELETE on audit_log raise 'append-only' on PostgreSQL 16)"]},{"id":"D2","state":"met","evidence":["test_audit.py::RecordTest.test_key_shaped_detail_rejected (422 audit.detail_secret, nothing stored)"]},{"id":"D3","state":"met","evidence":["test_audit.py::HttpTest.test_non_admin_403_and_non_member_404","test_audit.py::QueryTest.test_non_admin_forbidden"]}]}
```

# CMD-GC15 보고: audit 도메인

## 한 일
- `audit` 도메인: 추가 전용 `audit_log`(스키마의 트리거 사용), `record()` · `query()`, `GET /v1/workspaces/{ws}/audit-log`(admin 전용, 비멤버 404, 비admin 403, `action`/`from`/`to`/`cursor`/`limit`, 최신순 id 커서).
- `detail` 검사: 키 모양 문자열(PEM, AKIA, ghp_, sk-, xox, JWT, Bearer), 비밀 이름 필드(password/secret/token/api_key 등, `_count`/`_id`/`has_` 등은 허용), 크기 8KB 초과는 422로 거부하고 저장하지 않는다.
- baseline 확장분: `identity/api.py`(current_user, AuthError 재수출), `identity/router.py` 가 `set_audit_recorder(audit.api.record)` 호출, `workspace/_identity.py` 의 dotted-name 폴백 제거(이제 `identity.api` 직접 import).

## 파일
`backend/app/domains/audit/{service,pg_store,wiring,api,router}.py`, `audit/tests/{__init__,test_audit}.py`, `backend/app/domains/identity/{api.py,router.py}`, `backend/app/domains/workspace/_identity.py`.

## 테스트
`make check` 통과, `make test` 48건 통과, 도메인 테스트(identity·workspace·audit) 35건 통과, 항목 `check` 11건 통과(GC_SCHEMA_TEST_DSN 설정, PostgreSQL 16). fastapi/psycopg 가 없으면 해당 테스트는 skip.

## 알아둘 점
- `audit.api.record(action, actor, detail=None, *, workspace_id, target_kind, target_id, actor_kind, request_id)`. 위치 인자 순서가 identity/workspace 가 주입받는 `(action, actor, detail)` 과 같아 어댑터가 필요 없다. domain-model.md 의 `record(actor, action, target, detail)` 표기와 순서가 다르다(아래 요청 참고). workspace_id 와 target 은 detail 의 `workspace_id` / `<prefix>_id` 에서 유도한다.
- `record` 는 비밀 의심 detail 에 `AuditError`(422)를 던진다. 호출 도메인은 detail 에 id · 개수만 담아야 한다.
- 이 환경에서 로컬 PG 는 소켓 DSN(`postgresql:///postgres`)으로만 접속된다.

## baseline 요청
1. `workspace/wiring.py` 가 `set_audit_recorder(audit.api.record)` 를 호출하도록 연결(workspace 도메인 파일이라 이번 항목에서 손대지 않았다. 지금은 workspace 감사가 no-op).
2. `docs/domain-model.md` 의 audit 공개 인터페이스를 위 실제 시그니처로 갱신(contract 항목).
