```ga
{"schema":"report/2","from":"infra","handled":[{"id":"CMD-GC50","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc50","sha":"00e2687af57dd08ea9ce09affe1dcb05ea3e5020"}],"tests":{"passed":150,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["infra/tests/test_dev_env.py (names, no-overwrite, no printed value, KEK 32 bytes, config dump, compose names, make targets)","frontend/tests/shell/mode.test.ts","backend/tests/test_cors.py","mutations killed: overwrite, printed value, compose name mismatch, GC_KEK_ in dump"]},{"id":"D2","state":"met","evidence":["python3 scripts/e2e_stack.py: 1 passed against PostgreSQL 16 with pinned l0-telemetry and rlo-sdk installed","reports/gc50/{upload,overview,advisor,report}.png","make check 0; make test green (PY=venv, GC_SCHEMA_TEST_DSN set): 35+37+18 unittest, 60 vitest, 0 skipped"]},{"id":"D3","state":"met","evidence":["reports/CMD-GC50.md"]}]}
```

# CMD-GC50 보고

## 한 일
- **S1**: 프런트는 `NEXT_PUBLIC_API_URL` 하나만 읽고, compose도 같은 이름을 쓴다(`NEXT_PUBLIC_API_BASE` 제거). `NEXT_PUBLIC_API_MODE=real` 이면 모든 화면이 실제 클라이언트를 쓴다. 기본값은 fake 그대로(`isFakeMode`).
- **S2**: `scripts/dev_env.py` 가 `.env` 를 생성한다(`secrets.token_urlsafe`, `GC_KEK_ID=dev`, `GC_KEK_dev`=32바이트 base64, compose DB용 `DATABASE_URL`, CORS, 모드/URL). 기존 `.env` 는 덮어쓰지 않고, 값은 출력하지 않으며(이름만), 파일 권한 0600이다. `make dev` / `make dev-down` / `make dev-env` / `make dev-migrate`(스키마가 없을 때만 db 컨테이너 안에서 적용). README에 한국어 macOS 빠른 시작 두 경로(Docker Desktop, Homebrew postgresql@16 + uvicorn + next).
- **S3**: `.env.example` 에 `GC_KEK_<id>=`(패턴 줄), `NEXT_PUBLIC_API_MODE`, `NEXT_PUBLIC_API_URL`. `config.dump()` 를 새로 만들어 `GC_KEK_` 접두 변수를 전부 제외하고 비밀은 가린다.
- **S4**: `scripts/e2e_stack.py` 가 임시 DB를 만들고 api, worker, web(`next build` + `start`)을 띄워 health 를 기다린 뒤 Playwright 를 돌리고 모두 정리한다. `tests/e2e/gc50.spec.ts`: 가입 → 개인 워크스페이스 → Claude Code jsonl 업로드 → 수집 완료 → 개요 총 토큰 93,150 → 어드바이저 R1 발견 → 리포트 CSV 내보내기. 스크린샷 4장은 `reports/gc50/`.

## 실제 스택에서 찾은 결함
- **CORS 미설치**: `GC_CORS_ORIGIN` 은 읽히기만 하고 미들웨어가 없어서 브라우저의 `OPTIONS /v1/auth/signup` 이 405였다. `backend/app/main.py` 에 CORSMiddleware(credentials 허용, 설정된 origin만)를 추가했고 `backend/tests/test_cors.py` 로 고정했다.

## 파일
`scripts/dev_env.py`, `scripts/e2e_stack.py`, `tests/e2e/*`, `infra/docker-compose.yml`, `infra/tests/test_dev_env.py`, `.env.example`, `Makefile`, `README.md`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/tests/test_cors.py`, `frontend/src/lib/api/index.ts`, `frontend/tests/shell/mode.test.ts`, `docs/ownership.md`(새 스크립트 2줄), `.gitignore`.

## 테스트
- 핀 패키지(l0-telemetry, rlo-sdk)를 Python 3.12 venv에 설치하고 PostgreSQL 16을 로컬에서 띄워 `make test`(35+37+18 unittest, 60 vitest, skip 0)와 `make check` 모두 통과. e2e 1건 통과.
- 뮤턴트 4종(덮어쓰기, 값 출력, compose 이름 불일치, dump에 GC_KEK_ 노출) 모두 테스트가 실패시킨다.

## 열린 문제
- 웹에 리포트 화면과 소스 선택 UI가 없다. e2e 는 소스 생성과 리포트 생성/내보내기를 페이지 세션 토큰으로 API 직접 호출했고, 업로드, 개요, 어드바이저는 실제 화면으로 검증했다.
- 백엔드 `test_e2e.py` 의 Claude Code 파일(2호출)은 어드바이저 발견이 나오지 않아, e2e 는 같은 형식에 90k 컨텍스트 호출 1건을 더해 R1을 발생시킨다.
- Docker가 이 컨테이너에 없어 `make dev` 자체와 compose 경로는 실행해 보지 못했다(compose 파일 파싱과 환경 이름 일치만 테스트). 컨테이너 안 `npm install`/`pip install` 첫 기동 시간은 미측정.
- 개요 추세 차트는 1초 대기 후 캡처했으나 비어 보일 수 있다(캡처 타이밍 문제로 추정, 미확인).

## baseline 요청
- Docker Desktop(macOS)에서 `make dev` 한 번 실행해 db/api/worker/web 기동을 확인해 주세요.
- `python3 scripts/e2e_stack.py` 재실행(DATABASE_URL 은 CREATE DATABASE 가능한 DSN, 핀 패키지가 설치된 인터프리터).
- 웹 리포트 화면과 업로드 화면의 소스 선택은 frontend 후속 지시가 필요합니다.
