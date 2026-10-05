```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-GC43","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc43","sha":"3184d274ce3f5442e53c570385265acb0d8fbfdc"}],"tests":{"passed":8,"failed":0,"skipped":0},"change_size":"implementation","items":[{"id":"D1","state":"met","evidence":["frontend/tests/ops/ingest.test.ts: follows a scripted stream to done; resumes with Last-Event-ID after drop"]},{"id":"D2","state":"met","evidence":["frontend/tests/ops/ingest.test.ts: audit access admin-only; nav hides /audit for non-admin"]}]}
```

## 한 일
- 업로드 화면: `POST /uploads` 후 `ingest-jobs/{job}/events` SSE 를 따라가며 진행 막대 표시. 연결이 끊기면 마지막 `id` 를 `Last-Event-ID` 로 보내 재연결(`ingest-stream.ts`).
- 알림 화면: 목록과 읽음 처리. 감사 로그: admin 만 요청·표시(`access.ts`), nav 는 `adminOnly`.

## 파일
`frontend/src/app/(app)/{upload,notifications,audit}/**`, `frontend/tests/ops/ingest.test.ts`.

## 테스트
`npm --prefix frontend run test -- --run tests/ops` 8 passed. `tsc --noEmit` 통과. `make check`, `make test` 통과(스키마 테스트 1건 skip: DSN 없음). 전체 vitest 에서 `tests/components/gallery.spec.ts` 는 Playwright 용 빌드 산출물이 없어 vitest 로는 실패하며 이 항목 범위 밖이다.

## 열린 문제 / baseline 요청
- 업로드 화면은 fake API 가 multipart/SSE 를 지원하지 않아 실제 `fetch` 를 쓴다(fake 모드에서는 동작하지 않음). 요청: GC40 fake 에 SSE 스트림 핸들러 추가.
- 로그인 후 워크스페이스 ID 를 `setWorkspaceId` 로 저장하는 코드가 아직 없다(셸 담당).
