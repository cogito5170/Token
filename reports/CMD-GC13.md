```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC13","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc13","sha":"1e9e94a80039055c294db2cfe51699ad9862ed69"}],"tests":{"passed":15,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["test_password_never_stored_or_returned"]},{"id":"D2","state":"met","evidence":["test_reuse_revokes_family"]},{"id":"D3","state":"met","evidence":["test_expired_jwt_rejected"]},{"id":"D4","state":"met","evidence":["test_11th_login_in_15_min_refused"]}]}
```

## 한 일
identity 도메인: signup · login · refresh(회전, family 재사용 탐지) · logout · /v1/me. Argon2id(m=64MiB,t=3,p=1), HS256 JWT 15분(외부 의존 없음), 로그인 속도 제한(IP+이메일 10회/15분), 감사 훅(주입형 recorder, GC15 전까지 no-op), `identity.user.created` 이벤트 발행.

## 파일 (backend/app/domains/identity/)
tokens.py, passwords.py, service.py(MemoryStore 포함), pg_store.py, router.py, tests/test_identity.py

## 시험
identity unittest 15개 통과(argon2·fastapi 설치 시). 의존성이 없으면 Argon2·HTTP 시험 2개는 skip. make check, make test 통과. 병합: origin/claude/gracious-meitner-vp49xe. PgStore 는 실제 DB 로 시험하지 않았다(psycopg 없음).

## 열린 문제 / baseline 요청
- 요청: backend/app/main.py 소유자가 `/v1/me` 등 401 의 `HTTPException(detail={code,message})` 를 `{code,message}` 본문으로 바꾸는 예외 처리기를 추가(현재는 {"detail":{...}}).
- 요청: GC15 이후 `router.set_audit_recorder(audit.api.record)` 배선, 시작 시 `open_pool`.
- 로그인 속도 제한은 프로세스 메모리(다중 프로세스면 공유 안 됨).

## 다음 세션 참고
workspace(GC14)는 `app.domains.identity.router.current_user` 의존성을 사용(UserRow: id, email, display_name). 리프레시 쿠키 path=/v1/auth.
