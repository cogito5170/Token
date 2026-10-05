```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-GC42","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc42","sha":"c0116ffa5e4848aad00521c100acf262a9047c2a"}],"tests":{"passed":12,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["ESTIMATED: estimate/EstimateView draws RangeBand kind=ESTIMATED; budgets projection dashed (6 4) + band; tests/consulting"]},{"id":"D2","state":"met","evidence":["SIMULATED: what-if SimulationResult lists assumptions, dotted band"]},{"id":"D3","state":"met","evidence":["advisor: decideProposal refuses apply without confirm; ConfirmDialog shown only after 적용…"]},{"id":"D4","state":"met","evidence":["TITLE constants; compare/budgets titles asserted verbatim against docs/visualization.md"]}]}
```

## 한 일
컨설팅 화면 6 개 추가: compare(config_compare), budgets(budget_burn), advisor(findings + proposals + 적용 확인 대화상자), estimate(견적 폼 + 자체 측정 MAPE), what-if(가정 목록), profile. 각 라우트는 `page.tsx`(fetch) + 순수 `*View.tsx` + `nav.json`(consulting 그룹).

## 파일
`frontend/src/app/(app)/{compare,budgets,advisor,estimate,what-if,profile}/**`, `frontend/tests/consulting/consulting.test.ts`.

## 테스트
`npm --prefix frontend run test -- --run tests/consulting`: 12 통과. `tsc --noEmit`, `make check`, `make test` 통과. 전체 vitest 실행 시 `tests/components/gallery.spec.ts` 는 Playwright 용 `.build/gallery.html` 이 없어 실패(이 항목 이전부터 있던 문제, 이 항목 범위 밖).

## 알아둘 점
- 공유 컴포넌트가 classic JSX runtime 이라 vitest 에서 `globalThis.React` 를 지정해야 렌더된다(테스트에서 처리).
- budgets 임계값은 openapi 상 정수 퍼센트(1–100)로 해석.
- 시각화 질문 중 estimate/what-if/advisor/profile 제목은 visualization.md 에 정확한 question 이 없어(보조 화면) 질문형으로 새로 작성.

## baseline 요청
- 없음. (선택) vitest 설정에서 `tests/components` 를 제외하면 전체 `vitest --run` 이 깨끗해진다.
