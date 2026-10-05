```ga
{"schema":"report/2","from":"consulting","handled":[{"id":"CMD-GC32","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc32","sha":"c506a0e25c7b19a88df387b8e7c87060d00c90bb"}],"tests":{"passed":19,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["tests/test_profile.py::StatsTest.test_per_correct_matches_hand_computation (fixture: opus 3_000_000 micro/4 correct, haiku 600_000/5)"]},{"id":"D2","state":"met","evidence":["RecommendTest.test_evidence_below_five_never_recommended","RecommendTest.test_quality_floor_blocks","RecommendTest.test_default_floor_applies_when_unset"]},{"id":"D3","state":"met","evidence":["StatsTest.test_other_users_stats_never_returned","RouteTest.test_routes (u2 sees [])","HandoffTest.test_other_user_cannot_hand_off"]}]}
```

## 한 일

`backend/app/domains/profile/` 구현:

- `service.py`: 프로필 CRUD(검증, `store_bodies` 기본 false), `compute_stats`(작업 종류 × 모델 × 구조 × 맥락별 맞힌 작업당 토큰·비용, 전체 작업 비용 ÷ 정답 수, 반올림 정수), `recommend`(근거 ≥ 5, 정답률 ≥ 품질 하한(미설정 시 800‰), 현재 구성보다 저렴한 것 중 최저), `to_proposal`(advisor 로 넘김), MemoryStore.
- `pg_store.py`: profiles / personal_stats / recommendations PostgreSQL 저장소.
- `wiring.py`: 서비스 싱글턴, `usage.calls.ingested` · `usage.task.outcome_set` 구독 → 통계 갱신, `usage.api.tasks` 전 페이지 조회, `advisor.api.submit_proposal` 은 존재할 때만 연결(없으면 503, 테스트는 가짜 주입).
- `router.py`: `/v1/workspaces/{ws}/profile`(GET/PUT), `/profile/stats`, `/profile/recommendations`. 모두 `require_member`, 호출자 본인만.
- `api.py`: `get_profile`, `stats`, `refresh_stats`, `recommendations`, `to_proposal`.
- 테스트 19건(`tests/test_profile.py`, `tests/test_profile_pg.py`).

## 테스트
`make check` OK, `make test` 31+11+6 OK, 항목 check(unittest discover) 19건 OK. PostgreSQL 16 + fastapi + psycopg 가 있는 환경에서 실행(PG·route 시험은 의존성이 없으면 skip).

## 열린 문제 / baseline 요청
1. usage 작업(task)에 `user_id` 가 없다. 지금은 `user_id` 가 없는 작업을 워크스페이스의 모든 프로필 보유자에게 귀속한다. usage 가 task 에 `user_id` 를 내보내면 자동으로 사용자별로 갈린다(usage 항목 요청).
2. 추천을 advisor 로 넘기는 HTTP 경로가 openapi 에 없다(계약). `POST /v1/workspaces/{ws}/profile/recommendations/{id}/proposal` 추가를 요청한다. 서비스 `to_proposal` 은 준비돼 있다.
3. `first_try_success` 는 usage 작업에 필드가 있으면(`first_try_success` truthy) 센다. 현재 usage 는 내지 않아 0.
4. advisor.api 는 GC30 이후 연결. 인자 `(ws, origin, change, evidence)` 로 호출하고 반환의 `id` 를 쓴다.
5. 다음 세션: simulation(GC33)은 `profile.api.stats(ws, user)` 의 `tokens_per_correct` · `cost_*_per_correct` Metric 모양을 읽는다.
