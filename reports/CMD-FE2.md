```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-FE2","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/fe2","sha":"2827f32df5e3f631b329bd650f511bee31a5e640"}],"tests":{"passed":34,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["frontend/tests/monitor/scene.spec.ts: scene vs golden (10 golden t, toEqual minus recording)","frontend/src/monitor/scene.ts"]},{"id":"D2","state":"met","evidence":["frontend/tests/monitor/scene.spec.ts: determinism (frame + draw calls equal for t=0..12000 step 250, both modes)","frontend/tests/monitor/stage.spec.ts: same events + same t paint the same pixels twice; mounted Stage repeats"]},{"id":"D3","state":"met","evidence":["frontend/tests/monitor/scene.spec.ts: reduced motion (16 ms steps, only opacity differs; no dust/pulse/inner; fades <= max_fade_ms)","frontend/tests/monitor/stage.spec.ts: reduced motion pixels stay still; prefers-reduced-motion + still switch"]},{"id":"D4","state":"met","evidence":["frontend/tests/monitor/scene.spec.ts: words (fillText only the five words, equals scene words)","frontend/tests/monitor/stage.spec.ts: full replay records canvas text, body innerText empty, numbers only in hover tooltip"]}]}
```

# CMD-FE2 보고 — 라이브 모니터 무대

## 한 일

- **`scene(events, t)`** (`frontend/src/monitor/scene.ts`): `design/golden/reference.py` 를 TypeScript 로 옮긴 순수 함수. 10 개 golden 장면(`recording` 키 제외)과 정확히 같다. 입력 순서와 무관(seq 정렬).
- **`frame(events, t, {width,height,reduced})`** (`frame.ts`): 장면 뜻 → 그릴 목록(El[]). 배치 · 움직임도 순수 함수다. 
  대기 선반(위) · 무대(가운데, 타원 배치, pi 가 클수록 가까움, 협업 때 20 % 조임) · 완료 선반(아래) · 실패 선반(오른쪽) · 쉼 테두리(은퇴 figure 가 아래쪽 한 줄로 정렬).
  배치가 바뀌면 `travel`(800 ms) 동안 이동(재귀는 진행 중인 변화만, 최대 4 단계). figure 등장은 `slow` 로 0→1.
  크기 = 지름 24–72 px, 면적 ~ sqrt(tokens). 숨(halo)은 템포(`tempo_permille`) · 턴 경과로 빨라짐, 안쪽 입자 · 궤도 점, 고리 4 종, 연료 호(긴장 때 눈금), 메시지 펄스(20 개 넘으면 합침), 줄(tether), 자식 tile 점선, 버린 tile 점선 1 초, 먼지(pace, ≤ particles_max), 수평선(예산 사용, 긴장 때만 따뜻한 색).
- **움직임 줄이기**: 이동 · 숨 · 입자 · 펄스 · 먼지 없음. 상태는 즉시 바뀌고 불투명도 페이드 ≤ 120 ms, 메시지는 선 강조 1 초.
- **`draw(ctx, frame, theme)`** (`draw.ts`): 그리기만 한다. 색은 `design/tokens.json` themes(어두운/밝은), 글자는 다섯 단어만(그 밖의 단어는 그리지 않음).
- **`Stage.tsx`**: 전체 화면 canvas 하나. 라이브는 t = 지금 − 첫 이벤트, 재생은 t = 스크러버. 스크러버와 움직임 스위치(`still`)는 아래 막대에 마우스를 올릴 때만 보인다. 툴팁은 호버 때만, 12 px mono 숫자(일감 id · 토큰 · 경과 초, 선은 pi · 메시지 수, 수평선은 사용량/예산).
- **`feed.ts`**: SSE(`/monitor/sources/{source}/events`, Last-Event-ID 재접속, seq 중복 제거), 녹화 JSONL(`/recordings/{recording}`).
- **`/live`** 화면(`src/app/(app)/live/page.tsx`, nav.json 그룹 run): `?source=` 라이브, `&recording=` 재생, `?api=&ws=` 선택(데스크톱 사이드카용, ws 기본 nil UUID). `next build` 에서 정적 페이지로 빌드됨 확인.

## 바꾼 파일

`frontend/src/monitor/{scene,frame,draw,feed,encoding,types}.ts`, `frontend/src/monitor/Stage.tsx`, `frontend/src/app/(app)/live/{page.tsx,nav.json}`,
`frontend/tests/monitor/{scene.spec.ts,stage.spec.ts,fixture.ts,harness.tsx,.gitignore}`, 스크린숏 `frontend/tests/monitor/stage-{dark,light,reduced}.png`.
소유 밖 파일은 바꾸지 않았다(package.json 스크립트도 필요 없었음 — 루트 argv 가 그대로 돈다).

## 시험

- 항목 check `npx --prefix frontend playwright test tests/monitor`: 루트와 frontend/ 양쪽에서 **34 passed** (병합 뒤 다시 실행).
- `make check` 0 problem, secret scan 깨끗. `make test` (로컬 PostgreSQL 16, GC_SCHEMA_TEST_DSN): 31 OK · 11 OK(skipped 1) · 6 OK.
- `tsc --noEmit` 깨끗. `next build` 성공(/live 15.8 kB).
- done_when 규칙마다 깨지면 실패하는 시험: golden 비교, 프레임 · draw 호출 · 픽셀 결정성(그리고 t 가 다르면 달라짐), 움직임 줄이기에서 16 ms 간격 기하 불변(전체 움직임에선 움직임 = 공허하지 않음), 캔버스 fillText/strokeText 기록 + body innerText 비어 있음.

## 열린 문제

- `vitest`(npm test) 가 Playwright `*.spec.ts` 를 같이 집어 실패한다 — 기존 `tests/components/gallery.spec.ts` 도 같다(제 파일 2 개 추가). 또 `tests/shell/tokens.test.ts` · `api.test.ts` 가 생성물(tokens.css, schema.d.ts) 이 낡아 이미 실패 중이다(design/tokens.json · openapi 변경 뒤 `npm run gen` 안 됨). 둘 다 제 소유 밖.
- 스냅샷(`/snapshot`) 은 쓰지 않는다: 장면은 이벤트에서만 만들고, SSE 가 backfill 이벤트로 시작한다고 가정했다(fixture 첫 이벤트 `backfill: true`). backfill 이 없는 서버면 snapshot → 합성 이벤트 변환이 필요하다.
- figure 크기 한계(24/72 px)는 `encoding.figures.size` 문장에서 정규식으로 읽는다. 숫자 필드가 있으면 좋다.
- RN1 사이드카가 이 체크아웃에 없어 실제 SSE 와는 시험하지 못했다(파서 · 병합은 순수 함수).

## baseline 요청

1. design: `encoding.json figures` 에 `diameter_px: {min:24,max:72}` 같은 숫자 필드 추가(지금은 문장 파싱).
2. frontend(FE1 소유): vitest 가 `**/*.spec.ts` 를 제외하도록 설정, `npm run gen` 재실행으로 tokens.css · schema.d.ts 갱신.

## 다음 세션이 알 것

- 장면 뜻은 `scene()`, 배치 · 움직임은 `frame()`, 그리기는 `draw()` — 셋 다 순수, 벽시계는 `Stage.tsx` 의 rAF 한 곳에서만 읽는다.
- encoding.json 은 `import ... with { type: "json" }` 로 읽는다(Playwright ESM · Next 15 · esbuild 모두 통과).
- 브라우저 시험은 `tests/monitor/harness.tsx` 를 esbuild 로 묶어(`tests/monitor/.build/`, git 제외) setContent 로 띄운다. 스크린숏은 시험이 실행될 때마다 다시 쓴다(결정적이라 diff 없음).
- IF1(데스크톱)은 `/live?source=<id>&api=http://127.0.0.1:<port>` 로 띄우면 된다. 토큰은 지금 `getAccessToken()` 에서 읽으므로 사이드카 일회 토큰 전달 방식은 IF1 에서 정해야 한다.
