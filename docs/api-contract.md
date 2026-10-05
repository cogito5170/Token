# API 계약

원본: `docs/api/openapi.yaml` (OpenAPI 3.1). 검증: `python3 scripts/validate_openapi.py` (공식 3.1 구조 스키마 + JSON Schema 2020-12 + $ref · operationId · 경로 인자 검사). 이 문서는 규약을 적는다.

## 1. 규약

- 접두사 `/v1`. 워크스페이스 데이터는 `/v1/workspaces/{ws}/…` 아래에만 둔다. 서버는 모든 요청에서 `workspace.require_member(ws, user, min_role)` 를 먼저 부른다.
- 경로 항목마다 `x-domain` 이 정확히 하나다(`scripts/check_docs.py` 검사). 라우터 파일은 `backend/app/domains/<domain>/router.py` 이고, 그 도메인의 경로만 등록한다.
- `x-later: true` = Run 도메인, MVP 에서 구현하지 않는다(라우터 미등록, 프런트엔드는 화면을 숨긴다).
- 인증: `Authorization: Bearer <JWT>` (15 분). 리프레시는 httpOnly · Secure · SameSite=Strict 쿠키 `gc_refresh`, `/v1/auth/refresh` 에서 회전.
- 오류: `{code, message, request_id}`. `message` 에 업로드 내용 · 키 · 비밀번호를 넣지 않는다. 상태 코드: 400 형식, 401 인증, 403 역할, 404 범위 밖(존재 여부를 숨긴다), 409 상태 충돌, 413 크기, 422 의미 오류.
- 페이지: 커서 방식 `?cursor=` → 응답 `next_cursor`.
- 기간: `from`, `to` (RFC 3339, 반열린 구간 `[from, to)`), 기본 최근 30 일.
- 숫자: 토큰 · 금액은 JSON 정수. 금액 필드는 `*_microusd`. 지표는 `Metric {value, unit, provenance, coverage_permille?}`, 범위는 `Range {p10, p50, p90, unit, provenance}`, 시계열은 `Series {name, unit, provenance, points: [[ts, value]]}`.
- 비밀: `CredentialRef` 는 `additionalProperties: false` 이며 비밀값 필드가 없다. `secret` · `password` 는 `writeOnly`. 계약 시험(roadmap CMD-GC12)이 모든 응답 스키마에 `secret|password|api_key|token_hash|ciphertext` 이름의 필드가 없는지 검사한다(`access_token` 은 로그인 응답에서만 허용).

## 2. SSE

| 경로 | 이벤트 | 데이터 | 끝 |
|---|---|---|---|
| `GET /v1/workspaces/{ws}/ingest-jobs/{job}/events` (MVP) | `progress`, `done`, `failed` | `IngestJobEvent` (`seq`, `stage`, `pct`, `counts`) | `done` · `failed` 뒤 닫음 |
| `GET /v1/workspaces/{ws}/runs/{run}/events` (나중) | `node.started`, `turn`, `wait`, `node.retired`, `item.state` | `run_events` 행 | 실행 종료 |

- 형식: `id: <seq>\nevent: <name>\ndata: <json>\n\n`. 15 초마다 `: ping`.
- 재개: 브라우저가 보내는 `Last-Event-ID` 이후 seq 부터 DB(`ingest_job_events`)에서 재생 → 이어서 실시간. 그래서 프로세스가 재시작해도 이벤트가 빠지지 않는다.
- 구현: api 프로세스는 `LISTEN ingest_job_<id>` (워커가 이벤트 행 삽입 뒤 `NOTIFY`), 연결이 없으면 1 초 폴링으로 대체.
- 인증: EventSource 는 헤더를 못 보내므로 같은 출처 쿠키 + 짧은 수명 `?sse_token=` (60 초, 경로 한정) 중 하나. 토큰은 로그에 남기지 않는다(접근 로그에서 쿼리 제거).

## 3. 경로 ↔ 도메인 요약

| 도메인 | 경로 |
|---|---|
| identity | `/v1/auth/*`, `/v1/me` |
| workspace | `/v1/workspaces`, `/{ws}`, `/{ws}/members`, `/{ws}/projects` |
| source | `/{ws}/sources`, `/{ws}/uploads` |
| ingestion | `/{ws}/ingest-jobs`, `/{job}`, `/{job}/events` |
| usage | `/v1/models`, `/{ws}/usage/*` |
| quota | `/{ws}/budgets*`, `/{ws}/quota/alerts` |
| estimation | `/{ws}/estimates*`, `/{ws}/estimation/accuracy` |
| advisor | `/{ws}/advisor/*`, `/{ws}/proposals*` |
| simulation | `/{ws}/simulations*` |
| profile | `/{ws}/profile*` |
| report | `/{ws}/reports*` |
| notification | `/v1/notifications*`, `/v1/notification-prefs` |
| audit | `/{ws}/audit-log` |
| integration | `/{ws}/integrations`, `/{ws}/provider-credentials*` |
| run (나중) | `/{ws}/runs*` |

운영용 `/healthz`, `/readyz` 는 공개 계약 밖이다(`backend/app/main.py`, infra 담당, 인증 없음, 데이터 없음).

## 4. 계약 변경

openapi.yaml · schema.sql · domain-model.md · visualization.md 는 **공유 계약**이다. 바꾸려면 roadmap 의 contract 작업(`"kind": "contract"`)을 하나 만들고, 그 작업만 이 파일들을 소유한다. 변경 뒤 `check_docs.py` 와 `validate_openapi.py` 가 통과해야 한다.
