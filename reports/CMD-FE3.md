```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-FE3","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/fe3","sha":"ac56252d787f382138b5105aae5d6a1d67296202"}],"tests":{"passed":106,"failed":12,"skipped":23},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["cd frontend && npx vitest run: 9 files, 57 passed, 0 failed","npx playwright test: 46 passed; the 12 gallery snapshot tests fail identically on the untouched integration head (32 px diffs, container rendering), see open problems","Makefile test target runs vitest (tests/test_frontend_wiring.py)","make check 0 problems"]},{"id":"D2","state":"met","evidence":["stale tokens.css (duration-travel removed): tests/shell/tokens.test.ts 2 failed","stale schema.d.ts: tests/shell/api.test.ts 1 failed","'failed' removed from RING_BY_STATUS in scene.ts: tests/monitor/judge-red.test.ts 3 failed"]},{"id":"D3","state":"met","evidence":["reports/CMD-FE3.md with culprit commits","notify/1 sent to baseline"]}]}
```

# CMD-FE3 보고

## 한 일
- **S1 원인 커밋**: `tokens.test.ts` 2건과 `api.test.ts`의 sync 1건은 모두 `design/tokens.json`에 `motion.duration.travel`(800ms)을 추가한 **3f92e1d (CMD-DS3)** 이후 빨개졌다. GC40 재생성(c31a00c)이 그보다 앞서 있었고 DS3가 재생성을 하지 않았다. `api.test.ts`의 sync 테스트는 openapi 스키마와 함께 tokens.css도 검사하므로 같은 원인이다. `schema.d.ts`는 현재 openapi와 일치(변경 없음). 생성기는 올바르며 입력만 바뀌었으므로 `npm run gen`으로 `tokens.css`, `tokens.generated.ts`를 재생성했다(손편집 없음).
- 스펙 3건(`gallery.spec.ts`, `monitor/scene.spec.ts`, `monitor/stage.spec.ts`)은 vitest 설정이 아예 없어서 처음부터 수집됐다: gallery는 **bb68583 (CMD-FE1)**, scene/stage는 **f1373be (CMD-FE2)** 에서 추가된 순간부터 vitest에서 실패. `make test`가 프런트엔드를 돌리지 않아 아무도 몰랐다.
- **S2**: `frontend/vitest.config.ts` 신설 — `tests/**/*.test.ts`만 포함, `**/*.spec.ts` 제외. Playwright는 그대로 스펙을 소유.
- **S3**: `make test`가 `cd frontend && npm ci(없을 때) && npx vitest run`을 실행; node가 없으면 "SKIP frontend unit tests" 메시지. CI에 `actions/setup-node@v4`(22) 추가.
- **S4**: 설계 매핑에는 이미 실패 신호가 있다(`design/encoding.json`: `file:node.state.done` failed → 톱니 틈 고리 `jagged_gap`, `l0:work.failed`/queue.failed → 옆 선반의 갈라진 타일). 씬 모델과 프레임도 이미 구현돼 있었으나 **테스트가 없었다**. `tests/monitor/judge-red.test.ts` 추가: 실패 → 고리 `failed`/`jagged_gap` + 선반 `failed` 타일 + 프레임의 ring/split 요소; 이후 green 결과 → 고리 `verified`/`closed`로 해소. 신호를 새로 만들지 않았다.

## 변경 파일
.github/workflows/ci.yml, Makefile, tests/test_frontend_wiring.py, frontend/vitest.config.ts, frontend/tests/monitor/judge-red.test.ts, frontend/src/styles/tokens.css, frontend/src/lib/tokens/tokens.generated.ts (생성물 2개는 생성기 출력).

## 테스트
vitest 57 passed / 0 failed; playwright 46 passed, 12 failed(아래); make check 0; make test OK; 변이 3종 모두 검출(D2).

## 열린 문제
- Playwright `gallery.spec.ts`의 시각 스냅샷 12건은 통합 헤드(1d9fdbe)에서도 동일하게 실패(32px 차이, 컨테이너 폰트/렌더링 차). 내 변경과 무관해 스냅샷은 건드리지 않았다. CI 환경에서 확인 필요.

## baseline 요청
- 디자인 요청(선택): 데모 프레임 03-red-judge에서 실패 고리(톱니 틈, 2px, 본문색)와 갈라진 타일이 매우 작아 눈에 잘 띄지 않는다. 매핑대로 그려지긴 하나 "눈에 띄게" 하려면 design이 실패 신호의 크기/강조(예: 고리 굵기·톱니 진폭)를 `encoding.json`에 정의해야 한다. 임의로 만들지 않았다.
- 다음 세션: 디자인 토큰이 바뀌면 `cd frontend && npm run gen`을 같이 커밋할 것(이제 `make test`가 잡는다).
