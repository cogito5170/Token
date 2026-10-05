# 데스크톱 셸 (CMD-IF1, ADR-0008)

로컬 `.ga` 디렉터리를 **읽기만** 하는 라이브 모니터 앱. 제어 동작은 없다.

- `src/main.js` — Electron 메인. 읽기 전용 Python 사이드카를 `127.0.0.1` 에서 띄우고(일회용 토큰), 정적 Next.js export 를 `app://app/` 으로 서빙한다.
- `src/preload.js` — 렌더러에 `{sidecarUrl}` 만 노출한다. **토큰은 노출하지 않는다.** (로그인용 임시 토큰도 쓰지 않는다: 웹 Shell 이 `window.gaDesktop` 을 보고 `/live` 를 크롬 없이 렌더하고, `/live` 는 `gaDesktop.sidecarUrl` 을 우선 사용한다.)
- `src/security.js` — webPreferences, CSP, 프록시 허용 규칙.
- `sidecar/guard.py` — `python3 -m app.domains.run.sidecar` 를 감싸, 셸이 (SIGKILL 포함) 사라지면 stdin EOF 로 함께 종료한다.
- `scripts/build-renderer.mjs` — `frontend/` 를 복사해 `GC_STATIC_EXPORT=1` 로 빌드(정적 export) → `renderer/`. 복사본의 설정 파일을 덮어쓰지 않는다.
- `scripts/pack.mjs` — `dist/app` 에 배포용 트리(렌더러 + 셸 + 벤더링한 `app/domains/run/*.py`)를 만든다.

## 실행

```
npm --prefix desktop ci && npm --prefix desktop run build:renderer
npx --prefix desktop electron desktop --ga-dir /path/to/.ga
```

환경 변수: `GA_PYTHON`(기본 `python3`), `GA_BACKEND_DIR`, `GA_RENDERER_DIR`.

## 보안

- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, 새 창·webview·외부 이동 차단.
- CSP: `default-src 'none'`, 스크립트는 `'self'` + 인라인 스크립트 해시만, `connect-src 'self'`. 원격 콘텐츠 없음.
- ADR 과의 차이(더 엄격하게): 렌더러는 사이드카에 직접 붙지 않는다. 메인이 `app://app/v1/...` GET/HEAD 만 사이드카로 전달하면서 `Authorization` 을 붙인다. 그래서 토큰은 렌더러·디스크·로그 어디에도 없다.
- `.ga` 안에는 아무것도 쓰지 않는다(사이드카에 `--record-dir` 를 주지 않는다).

## 테스트

`npx --prefix desktop playwright test` (AppImage 테스트는 `npm run dist:linux` 후에만 실행, 아니면 skip) — Xvfb 를 자동으로 띄운다. root 로 실행하면 Chromium 샌드박스 헬퍼를 쓸 수 없어 테스트에서만 `--no-sandbox` 를 붙인다(창의 `sandbox: true` 설정은 그대로 검증한다).

## 설치 파일 (CMD-IF2)

`electron-builder`(고정 버전, devDependency)로 만든다. 먼저 `npm run build:renderer` 가 필요하다.

| 플랫폼 | 명령 | 결과 (`dist/installers/`) | 어디서 |
|---|---|---|---|
| Linux | `npm run dist:linux` | `GA Console Monitor-<ver>.AppImage` | 이 컨테이너에서 빌드·실행 확인 |
| macOS | `npm run dist:mac` | `.dmg` (서명 없음) | **Mac 에서만** 빌드 가능 |
| Windows | `npm run dist:win` | NSIS `.exe` (서명 없음) | Windows(또는 wine) 에서 빌드 |

앱 id `dev.gaconsole.monitor`, 제품명 `GA Console Monitor`, 아이콘은 `build/icon.png` 자리표시자다. 설치 파일에는 Python 3 가 포함되지 않는다: 실행하는 PC 에 `python3` 가 있어야 하고(`GA_PYTHON` 으로 지정), 앱은 `asar` 없이 패키징된다(사이드카 `.py` 를 직접 실행하기 때문).

헤드리스 확인: `APPIMAGE_EXTRACT_AND_RUN=1 "GA Console Monitor-0.0.1.AppImage" --no-sandbox --ga-dir <.ga>` (root 일 때 `--no-sandbox`).

### Mac / Windows 에서 빌드하기 (서명 없이)

1. `git clone` 후 `npm --prefix desktop ci && npm --prefix desktop run build:renderer`
2. Mac: `npm --prefix desktop run dist:mac`, Windows: `npm --prefix desktop run dist:win`. 서명되지 않은 파일은 Gatekeeper/SmartScreen 경고가 뜬다.
3. 서명·공증은 소유자의 자격 증명이 필요하다(아래). 저장소에 넣지 않고 빌드 머신의 환경 변수로만 준다: macOS `CSC_LINK`, `CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` (그리고 `mac.identity`/`notarize` 설정), Windows `CSC_LINK`, `CSC_KEY_PASSWORD`(코드 서명 인증서).

## 데모 (구동 장면)

- `demo/replay.py` — 6 개 노드(design, frontend, core-backend, verifier, judge, integration)의 약 40 초짜리 실행을 시스템 임시 디렉터리의 `.ga` 에 재생한다(턴, 노드 간 메시지, 빨간 judge → 초록, integration). 임시 디렉터리 밖에는 아무것도 쓰지 않는다. 사용자의 `.ga` 는 건드리지 않는다.
- `demo/record.mjs` — 앱(AppImage 가 있으면 그것)을 재생 대상으로 띄워 `demo/out/`(git 무시)에 영상(webm 1280x800)과 스크린샷 4 장을 만든다. `--preview` 를 주면 `demo/preview/` 에도 복사한다. `npm run demo`.
- 검토용 사본: `demo/preview/` (스크린샷 4 장 + `demo.webm`).
