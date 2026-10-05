```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-FE1","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/fe1","sha":"08253d17c35b161343ed99b33906b9c60cda3ba5"}],"tests":{"passed":24,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["frontend/tests/components/__snapshots__: 16 png (8 components x light/dark)","gallery.spec.ts: snapshot x16"]},{"id":"D2","state":"met","evidence":["gallery.spec.ts: chips differ by line style, not color"]},{"id":"D3","state":"met","evidence":["gallery.spec.ts: axe finds no violations (light, dark)"]},{"id":"D4","state":"met","evidence":["gallery.spec.ts: numbers use tabular-nums"]}]}
```

## 한 일
- `frontend/src/components/`: KpiTile, StatusChip, RangeBand, CostPair, BarList, FigureCard, KanbanColumn, EvidenceDrawer, 전용 `components.css`(디자인 토큰 `--gc-*` 만 사용), 갤러리 `Gallery.tsx`(정적 fixture).
- `frontend/playwright.config.ts`, `frontend/tests/components/` (global-setup, gallery.spec.ts, 스냅샷 16장).
- 칩은 같은 중립색에 테두리 모양(실선·채움/실선·파선·점선)으로 구분. 비용은 `formatMicroUsd`, 모르는 값은 `—`.

## 테스트
- `cd frontend && npx playwright test tests/components`: 24 passed (스냅샷 16, axe 2, 칩 2, tabular-nums 2, 빈값 2). make check, make test, tsc 통과.
- Playwright 자체 JSX 변환이 React 19 와 충돌해, global-setup 이 esbuild 로 Gallery 를 묶어 정적 HTML 로 렌더하고 spec 은 `page.setContent` 로 연다.

## 열린 문제 / baseline 요청
1. **`frontend/package.json` (GC40 소유)에 devDependencies 추가 요청:** `@playwright/test` 1.56.1, `@axe-core/playwright`, `esbuild`(현재는 vitest 가 끌어옴). 이 세션은 `npm i --no-save` 로만 설치했다. 스냅샷은 linux chromium 기준(`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`).
2. **check argv 실행 위치:** `npx --prefix frontend playwright test tests/components` 는 저장소 루트에서 실행하면 설정 파일을 못 찾는다(npx --prefix 는 cwd 를 바꾸지 않음). `frontend/` 에서 실행하거나 roadmap 의 argv 를 `npm --prefix frontend exec -- playwright test ...` 가 아닌 cwd=frontend 방식으로 바꿔야 한다. 루트 설정 파일은 이 항목 소유 밖이다.
3. 갤러리 라우트(`frontend/src/app/**`)는 소유 밖이라 만들지 않았다. 필요하면 `import { Gallery } from "../components"` 를 마운트하는 경로를 GC40/GC41 쪽에서 추가. `components.css` 는 전역 CSS 에서 `@import` 해야 화면에 적용된다.

## 다음 세션이 알 것
- 컴포넌트는 서버 렌더 가능한(훅 없는) 순수 컴포넌트다. 값은 호출자가 포맷해서 넘긴다(KpiTile value 는 문자열).
- 스냅샷 갱신: `cd frontend && npx playwright test tests/components --update-snapshots`.
