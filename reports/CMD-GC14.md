```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC14","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc14","sha":"7ec761b87b45aa3e60590e0325c666414254a38c"}],"tests":{"passed":9,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["tests.test_workspace.BoundaryTest.test_non_member_gets_404_on_another_workspace","tests.test_workspace.BoundaryTest.test_viewer_cannot_create_project","tests.test_workspace.PersonalWorkspaceTest.test_user_created_makes_personal_workspace_once","make check and make test green"]}]}
```

## 한 일
워크스페이스 도메인(`backend/app/domains/workspace/`): 서비스(역할 viewer<developer<admin), 메모리 · PostgreSQL 저장소, `/v1/workspaces*` 라우터, 공개 `api.require_member(ws, user_id, min_role)`.
- 비구성원 · 잘못된 uuid · 없는 ws → 404(존재 숨김), 구성원이지만 역할 부족 → 403.
- 프로젝트 생성은 developer 이상, 구성원 추가는 admin. 이름 중복 409.
- `identity.user.created` 구독 → "Personal" 워크스페이스(slug `personal-<id 앞 8자>`, admin) 멱등 생성.
- audit 은 `set_audit_recorder` 로 GC15 연결 대기(현재 no-op), detail 은 id · 역할만.

## 파일
`__init__.py` 외 `service.py`, `pg_store.py`, `api.py`, `wiring.py`, `router.py`, `_identity.py`, `tests/test_workspace.py`.

## 시험
item check 9 passed(fastapi 설치 시 HTTP 시험 포함, 없으면 skip). `make check` · `make test` 통과(PostgreSQL 시험은 DSN 없어 skip, pg_store 는 실DB 미검증).

## 열린 문제 / baseline 요청
- identity 에 `api.py` 없음 → 경계 규칙상 `identity.router` 직접 import 불가. `_identity.py` 가 `identity.api.current_user` 를 우선 시도하고 없으면 dotted-name 으로 fallback. **요청: GC13 소유 파일에 `identity/api.py`(`current_user` 재수출) 추가**, 이후 fallback 제거.
- 개인 워크스페이스 이름은 payload 에 user_id 만 있어 고정 "Personal".
- 라우터는 `require_member` 를 라우터와 서비스에서 두 번 호출(저렴한 조회). members 조회에 email 은 users 조인.
- 다음 세션: 다른 도메인은 `from app.domains.workspace.api import require_member` 사용. 라우터 마운트는 `build_router` 가 자동 처리.
