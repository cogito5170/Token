```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-GC41","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc41","sha":"e34f1f1738747ddf5d17b5608b07c86c879326e7"}],"tests":{"passed":12,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["frontend/tests/usage/usage.test.ts: each screen's loader calls only its listed paths (fake API spy)"]},{"id":"D2","state":"met","evidence":["overview renders CostPair (list and cli side by side) for cost and cost per correct task"]},{"id":"D3","state":"met","evidence":["cli coverage chip '부분 n%' appears below 1000 permille and is absent at 1000 (test)"]}]}
```

## 한 일
- `overview`(타일 5 블록 = 지표 7 개, 비용 두 기준 나란히, 일별 추세), `token-mix`(누적 영역, 전체/모델별 전환, 구성 비율), `call-size`(log2 히스토그램, 임계선, 이상치, 이상치 호출 목록)를 docs/visualization.md 대로 구현. 화면마다 load.ts(API 경로) · View.tsx(순수) · page.tsx(연결)로 나눴다.
- 구성 요소 갤러리를 `/overview/gallery` 에 마운트, components.css 는 각 page.tsx 에서 import.
- 공용 ECharts 래퍼 `overview/EChart.tsx`(token-mix, call-size 도 사용).

## 변경 파일
frontend/src/app/(app)/{overview,token-mix,call-size}/**, frontend/tests/usage/usage.test.ts.

## 테스트
vitest tests/usage 12 통과(타일 출처 고정 테스트 추가), tsc 통과, next build 통과, make check / make test 통과.

## 열린 문제
- 화면은 워크스페이스 ID 를 sessionStorage(shell 스위치가 설정)에서 읽는다. /workspaces 를 따로 부르지 않기 위함.
- call_size 의 R1 finding 절감액 ESTIMATED 칩은 연결 API 가 interfaces 에 없어 미구현.
- 차트 DOM 은 vitest(node)에서 렌더하지 않고 옵션 빌더와 정적 마크업으로 검증. 빌드(next build)가 tsconfig.json 을 바꾸므로 커밋하지 않았다.
- vitest 설정 파일이 없어 테스트가 classic JSX 로 컴파일됨: 테스트에서 globalThis.React 를 설정.

## baseline 요청
- 없음(components.css import 는 각 page.tsx 에서 처리). 차트 토큰 파일 경로가 visualization.md 는 chart-theme.ts, 실제는 lib/charts/theme.ts 로 문서와 다르다(문서 정정 요청).
