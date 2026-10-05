# 데스크톱 셸 (CMD-IF1, ADR-0008)

로컬 `.ga` 디렉터리를 **읽기만** 하는 라이브 모니터 앱. 제어 동작은 없다.

- `src/main.js` — Electron 메인. 읽기 전용 Python 사이드카를 `127.0.0.1` 에서 띄우고(일회용 토큰), 정적 Next.js export 를 `app://app/` 으로 서빙한다.
- `src/preload.js` — 렌더러에 `{sidecarUrl}` 만 노출한다. **토큰은 노출하지 않는다.**
- `src/security.js` — webPreferences, CSP, 프록시 허용 규칙.
- `sidecar/guard.py` — `python3 -m app.domains.run.sidecar` 를 감싸, 셸이 (SIGKILL 포함) 사라지면 stdin EOF 로 함께 종료한다.
- `scripts/build-renderer.mjs` — `frontend/` 를 복사해 `output: "export"` 로 빌드 → `renderer/` (frontend 는 수정하지 않는다).
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

`npx --prefix desktop playwright test` — Xvfb 를 자동으로 띄운다. root 로 실행하면 Chromium 샌드박스 헬퍼를 쓸 수 없어 테스트에서만 `--no-sandbox` 를 붙인다(창의 `sandbox: true` 설정은 그대로 검증한다).
