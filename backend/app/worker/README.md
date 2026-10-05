# 워커 프로세스 (`python -m app.worker`)

워커는 `ingest_jobs` 를 claim(`FOR UPDATE SKIP LOCKED`)해 파이프라인을 돌린다. 이벤트 버스(`app/core/events.py`)는
**프로세스 안**에서만 전달되므로, 이벤트를 발행하는 프로세스에서 구독자를 설치해야 한다.
조립 코드는 `app/api/wiring.py` 의 `wire_worker()` / `wire_api()`.

## 이벤트가 발행되는 곳

| 이벤트 | 발행 프로세스 | 이유 |
|---|---|---|
| `usage.calls.ingested` | 워커 | `usage.api.load_calls` 는 인제스트 단계에서만 호출된다 |
| `ingestion.job.progressed/finished/failed` | 워커 | `IngestService.run_one` |
| `usage.task.outcome_set` | API | `PATCH /usage/tasks/{task}` |
| `identity.user.created` | API | signup |
| `source.upload.stored` | API | 업로드 |
| `advisor.proposal.created` | 워커(규칙 실행) 와 API(시뮬레이션·프로필의 제안) | 양쪽 |

## 워커가 설치하는 것

- `ingestion.adapters.register_all()`: 형식 어댑터(파싱은 워커에서만 일어난다). 없으면 모든 작업이 `unsupported_format`.
- `advisor.wiring.subscribe()`: `usage.calls.ingested` → 규칙 실행(finding · 제안). 인제스트 직후 findings 가 생기려면 워커에 있어야 한다.
- `profile.wiring.subscribe()`: `usage.calls.ingested` → 개인 통계 갱신.
- `source.wiring.subscribe()`: `ingestion.job.finished` → 업로드 purge 시계 재시작.
- `notification.wiring.subscribe(bus)`: `ingestion.job.finished/failed`, `advisor.proposal.created` → 알림.

API 프로세스는 같은 구독자에 더해 `workspace`(`identity.user.created`)를 구독한다. API 쪽의 advisor/profile 구독은
API 에서 발행되는 이벤트(`usage.task.outcome_set` 등)를 위한 것이다.

## 열린 문제 (만들지 않음)

1. **프로세스 간 이벤트(아웃박스, CMD-GC22 요청 3)**: 워커가 발행한 이벤트는 API 프로세스의 구독자에게 닿지 않는다.
   지금은 위처럼 "이벤트가 발행되는 프로세스에 구독자를 설치"로 우회한다. API 에서만 동작해야 하는 구독자가 워커 이벤트를
   받아야 하면(예: 실시간 푸시) `domain_events` 아웃박스 + 폴링/LISTEN 이 필요하다. 이 항목에서 만들지 않았다.
2. **quota 경보 평가 시점**: `quota.api.evaluate(ws)` 를 인제스트 후 호출하는 구독자와 `quota.alert.raised` → notification 의
   `notify` 연결은 아직 없다.
3. **멈춘 claim 회수(CMD-GC22 요청 4)**: `parsing` 에서 워커가 죽으면 작업이 남는다.
4. 워커 한 대가 한 번에 한 작업을 처리한다(동시성은 프로세스 수로 확장).
