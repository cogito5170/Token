```ga
{"schema":"report/2","from":"frontend","handled":[{"id":"CMD-GC40","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc40","sha":"25838ce40c5e3012f4682e62ab171dd59989828e"}],"tests":{"passed":16,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["frontend/tests/shell/api.test.ts: client types compile (tsc) + schema in sync with openapi.yaml"]},{"id":"D2","state":"met","evidence":["frontend/tests/shell/tokens.test.ts: CSS variables equal design/tokens.json"]},{"id":"D3","state":"met","evidence":["frontend/tests/shell/format.test.ts: 1234 micro-USD -> $0.0012, null -> em dash"]}]}
```

## 한 일
Next.js 셸: 인증 페이지(login/signup), 워크스페이스 전환기, 왼쪽 내비(사용 현황 / 실행 / 컨설팅 + 하단), openapi.yaml 에서 생성한 타입 API 클라이언트, fake API(fetch 대체 + 호출 스파이), design/tokens.json 에서 생성한 CSS 변수와 ECharts 테마, 금액·토큰 포매터, 파일시스템 라우트 레지스트리.

## 변경 파일
frontend/package.json(+package-lock.json), tsconfig.json, next.config.mjs, src/app/{layout,page}.tsx, src/app/(auth)/**, src/lib/**(api, auth, charts, format, gen, nav, shell, tokens), src/styles/**, tests/shell/**.

## 테스트
`npm --prefix frontend run test -- --run tests/shell` 16 통과. make check · make test 통과. `next build` 성공.

## 다음 세션이 알아야 할 것
- 생성물(src/styles/tokens.css, src/lib/tokens/tokens.generated.ts, src/lib/api/schema.d.ts)은 커밋되어 있다. tokens.json 이나 openapi.yaml 이 바뀌면 `npm --prefix frontend run gen` 을 돌려야 하며, 안 돌리면 tests/shell 이 실패한다(의도).
- 화면 등록: `src/app/(app)/<route>/nav.json` = {"group":"usage|run|consulting|footer","label","order","adminOnly"} 만 두면 내비에 나타난다. 공유 파일 수정 없음. 내비는 빌드 시점에 스캔한다(새 화면은 재빌드/dev 재시작).
- API 사용: `api()` (src/lib/api). NEXT_PUBLIC_API_MODE 기본값 fake; 실제 백엔드 연결 시 "real" 로. 테스트는 createFakeFetch(extra handlers) 와 .calls 스파이를 쓴다.
- 포매터: 1 달러 미만 4자리, 이상 2자리; null → "—".

## baseline 요청
- 소유 파일 목록 밖이지만 필요했던 frontend/package-lock.json 을 커밋했다(소유 표에 추가 요청). vitest 설정 파일은 두지 않았다(기본값 사용).
- IBM Plex 글꼴 self-host(ADR-0009)는 이 항목 범위 밖이라 CSS 변수만 선언했다; 후속 항목 필요.
