# ga Console

Token service platform built **with** ga-sdk (not a change to it): ingests AI usage records, visualizes tokens / cost /
quality, and consults (estimates, token-saving advice, personalization). Product spec: `docs/00-product-spec.md`.

- Architecture and contracts: `docs/` (start at `docs/architecture.md`), file ownership `docs/ownership.md`,
  parallel plan `docs/roadmap.md`.
- `make check` — contract consistency (`scripts/check_docs.py`) and OpenAPI validation.
- `make test` — skeleton tests, including the mutation tests of check_docs.
- `make backtest` — estimator baseline MAPE on the vendored FINAL_TASK results.
- `make db-up` / `make migrate` / `make secret-scan` — dev DB, 마이그레이션 적용, 비밀 패턴 검사(`infra/README.md`). 환경변수 이름: `.env.example`.

## 빠른 시작 (macOS, 개발용)

`.env` 의 값은 `scripts/dev_env.py` 가 이 컴퓨터에서 새로 생성한다(개발 전용, 커밋 금지, 값은 출력하지 않음). 이미 `.env` 가 있으면 덮어쓰지 않는다.

### A. Docker Desktop

```sh
make dev          # .env 생성(없을 때) + db, api, worker, web 시작 + 마이그레이션
open http://localhost:3000/signup
make dev-down     # 중지(데이터 유지)
```

첫 실행은 컨테이너 안에서 패키지를 설치하므로 몇 분 걸린다(`docker compose -f infra/docker-compose.yml --env-file .env logs -f`).

### B. Docker 없이 (Homebrew PostgreSQL 16 + uvicorn + next)

```sh
brew install postgresql@16 node python@3.12 && brew services start postgresql@16
export PATH="$(brew --prefix postgresql@16)/bin:$PATH"
createdb gaconsole && psql gaconsole -v ON_ERROR_STOP=1 -qf docs/schema.sql

python3 scripts/dev_env.py --db-host localhost       # POSTGRES_PASSWORD 는 쓰지 않으므로 DATABASE_URL 을 로컬 DB 로 바꾼다:
sed -i '' 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://localhost/gaconsole|; s|^GC_UPLOAD_DIR=.*|GC_UPLOAD_DIR=/tmp/gc-uploads|' .env
set -a; . ./.env; set +a

python3.12 -m venv .venv && .venv/bin/pip install -e backend
(cd backend && ../.venv/bin/uvicorn app.main:create_app --factory --port 8000) &   # api
(cd backend && ../.venv/bin/python -m app.worker) &                                # worker
(cd frontend && npm ci && npm run dev)                                             # web http://localhost:3000
```

브라우저에서 `http://localhost:3000/signup` → 가입 → 업로드(Claude Code `.jsonl`) → 개요/어드바이저/리포트. 웹은 `NEXT_PUBLIC_API_MODE=real` 일 때만 실제 API(`NEXT_PUBLIC_API_URL`)를 쓴다(기본은 가짜 API).
브라우저 e2e(`tests/e2e/`): `python3 scripts/e2e_stack.py` (로컬 PostgreSQL 16 과 `DATABASE_URL` 필요).
