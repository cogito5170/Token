# ADR-0003 DB 와 시계열, 작업 큐

- 상태: 채택
- 결정:
  - PostgreSQL 16 하나. 시계열 `usage_calls` 는 일반 테이블 + `(workspace_id, occurred_at)` 인덱스, 일별 집계 `usage_daily` 를 적재 트랜잭션에서 갱신.
  - 작업 큐도 PostgreSQL: `ingest_jobs` 를 `SELECT … FOR UPDATE SKIP LOCKED` 로 claim, 진행은 `ingest_job_events` + `LISTEN/NOTIFY`.
  - 마이그레이션: `backend/migrations/NNNN_*.sql` 평문 SQL, `0001` = docs/schema.sql.
- 이유: MVP 데이터량(사용자당 하루 수천 호출)은 일반 테이블로 충분하다. 큐를 DB 에 두면 Redis 등 구성 요소가 하나 줄고, 작업 상태와 데이터 적재가 같은 트랜잭션에 있다.
- 다시 볼 조건: `usage_calls` 가 1 억 행을 넘거나 차트 API P95 가 500 ms 를 넘으면 TimescaleDB 하이퍼테이블(같은 열, `occurred_at` 청크)과 연속 집계로 바꾼다. 큐 처리량이 초당 수십 작업을 넘으면 전용 큐를 검토한다. 둘 다 API 계약은 바뀌지 않는다.
