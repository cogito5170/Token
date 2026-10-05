```ga
{"schema":"report/2","from":"infra","handled":[{"id":"CMD-IF1","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/if1","sha":"acf7dd46724d314fc7a44e81cb9c8305d41223af"}],"tests":{"passed":10,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["desktop/tests/shell.spec.ts: launches against a fixture .ga dir and shows the stage (canvas paints; screenshot desktop/tests/electron-window.png)"]},{"id":"D2","state":"met","evidence":["shell.spec.ts: renderer has no Node access (require/process/module/Buffer undefined; contextIsolation, sandbox, nodeIntegration verified via getLastWebPreferences)","unit.spec.ts: webPreferences hardened"]},{"id":"D3","state":"met","evidence":["shell.spec.ts: the sidecar dies with the app (graceful quit and SIGKILL)"]},{"id":"D4","state":"met","evidence":["shell.spec.ts: nothing is written inside the .ga dir (mtime+sha256 tree compare, incl. a DELETE attempt)"]},{"id":"D5","state":"met","evidence":["shell.spec.ts: strict CSP, no remote content, GET-only proxy; token never logged or written to disk"]}]}
```

# CMD-IF1 보고 — 데스크톱 셸

## 한 일
ADR-0008 대로 Electron 셸을 `desktop/` 에 구현했다. 메인이 읽기 전용 Python 사이드카를 `127.0.0.1` 에서 일회용 토큰으로 띄우고, 정적 Next.js export(`/live`)를 `app://app/` 으로 서빙한다. 렌더러는 `app://app/v1/...` (GET/HEAD 만) 로 읽고, 메인이 `Authorization` 을 붙여 사이드카로 전달한다 → 토큰은 렌더러·디스크·로그에 없다(ADR 보다 엄격; preload 는 `{sidecarUrl}` 만 노출).

## 파일
`desktop/src/{main,preload,security,sidecar}.js`, `desktop/sidecar/guard.py`(셸이 SIGKILL 로 죽어도 stdin EOF 로 사이드카 종료; 내부에서 `python3 -m app.domains.run.sidecar` 실행), `desktop/scripts/{build-renderer,pack}.mjs`, `desktop/tests/*`, `desktop/README.md`.

## 테스트 / 결과
- `cd desktop && npx playwright test` (= done_when): 10 passed. Xvfb 자동 기동, 렌더러 없으면 빌드.
- done_when 규칙마다 변이 확인: `sandbox:false` → Node 접근 테스트 실패, guard 의 `os._exit` 제거 → 사이드카 종료 테스트 실패, 사이드카에 `--record-dir` 를 .ga 안으로 → no-write 테스트 실패.
- `make check`, `make test` 통과 (origin/claude/gracious-meitner-vp49xe 병합 후 재실행).

## 열린 문제
- root 컨테이너라 Chromium 샌드박스 헬퍼를 못 써서 테스트에서만 `--no-sandbox` 를 붙임(창 설정 `sandbox:true` 는 검증).
- `npx --prefix desktop playwright test` 는 cwd 가 `desktop/` 일 때 설정을 찾는다(frontend 의 같은 형태 check 와 동일 가정). 루트 cwd 에서는 설정 파일이 없어 동작하지 않는다.
- 렌더러 빌드는 `frontend/` 를 복사해 `output:"export"` 로 빌드(`desktop/.build`, 네트워크 필요 `npm ci`).
- 인라인 스타일 때문에 `style-src 'unsafe-inline'` 허용(스크립트는 해시만).

## baseline 요청
1. frontend: `next.config.mjs` 에 정적 export 옵션(`output:"export"`, `trailingSlash`, `images.unoptimized`)을 환경변수로 켜는 설정 — 지금은 빌드 스크립트가 복사본에서 덮어씀.
2. frontend: `Shell` 이 토큰 없으면 /login 으로 보내므로, `window.gaDesktop` 이 있으면 `/live` 에서 로그인 리디렉션 생략(+ 크롬 없이 렌더). 지금은 preload 가 sessionStorage 에 고정 placeholder(`desktop-local-placeholder`, 비밀 아님)를 넣어 우회.
3. frontend: `/live` 가 `window.gaDesktop.sidecarUrl` 을 읽도록(현재는 URL 쿼리 `api` 로 전달).

## 다음 세션
위 1–3 반영 후 placeholder 우회 제거; electron-builder 설정으로 설치 파일 생성.
