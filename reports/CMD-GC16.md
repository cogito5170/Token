```ga
{"schema":"report/2","from":"core-backend","handled":[{"id":"CMD-GC16","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc16","sha":"ab505e5b7b9eb64afe3e77aebdcc80ecec24e683"}],"tests":{"passed":10,"failed":0,"skipped":2},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["notification/tests/test_notification.py::EventTest.test_each_event_yields_one_notification_per_recipient"]},{"id":"D2","state":"met","evidence":["PrefTest.test_disabled_pref_suppresses_only_that_kind_and_user"]},{"id":"D3","state":"met","evidence":["ReadTest.test_mark_read_and_unread_filter","ReadTest.test_mark_read_unknown_or_foreign_is_404"]}]}
```

## 한 일
`backend/app/domains/notification/` 구현: `service.py`(알림 생성 · 목록 · 읽음 · 설정 · 이벤트 핸들러), `pg_store.py`, `wiring.py`(구독 + 서비스 싱글턴), `api.py`(`notify`, `list_notifications`, `mark_read`), `router.py`(/v1/notifications, /v1/notifications/{id}/read, /v1/notification-prefs).
- 이벤트 4종(`quota.alert.raised`, `ingestion.job.finished/failed`, `advisor.proposal.created`)마다 수신자당 알림 1건. 수신자는 payload 의 `user_id`, 없으면 `workspace_id` 의 전 멤버. 둘 다 없으면 무시.
- (kind, in_app) 설정이 꺼져 있으면 억제. 설정 없음 = 켜짐. 본문은 고정 템플릿 + 숫자 · id 만(자유 텍스트 미반영).
- 읽음: 남의 알림 · 없는 id 는 404, 두 번 눌러도 첫 read_at 유지.

## 테스트
check argv: 11 tests, 10 passed, 1 skipped(fastapi/psycopg 없을 때 라우터 테스트). make check · make test 통과(origin/claude/gracious-meitner-vp49xe 병합 후). 스키마 DB 테스트는 이 항목에 없음(PgStore 는 DB 로 검증하지 않음).

## 열린 문제
- PgStore 는 실제 PostgreSQL 에서 실행해 보지 않았다.
- payload 키(`alert_id`, `job_id`, `proposal_id`, `threshold_pct`, `user_id`, `workspace_id`)는 발행 도메인 구현 전이라 내가 가정했다. 발행 쪽이 다르면 `_TEMPLATES` 만 고치면 된다.

## 추가 (baseline 승인)
\`workspace.api.member_ids(ws)\` 와 \`WorkspaceService.member_ids\` 추가(테스트 \`test_member_ids_lists_all_members\`). notification 의 workspace fan-out 은 이 함수를 쓴다(\`FanOutTest\`, fastapi 가 없으면 skip).

## 다음 세션 참고
알림 kind 는 이벤트 이름 그대로. 이메일 · Slack 채널 설정은 저장만 하고 전송은 없다.
