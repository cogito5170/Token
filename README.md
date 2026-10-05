# ga Console

Token service platform built **with** ga-sdk (not a change to it): ingests AI usage records, visualizes tokens / cost /
quality, and consults (estimates, token-saving advice, personalization). Product spec: `docs/00-product-spec.md`.

- Architecture and contracts: `docs/` (start at `docs/architecture.md`), file ownership `docs/ownership.md`,
  parallel plan `docs/roadmap.md`.
- `make check` — contract consistency (`scripts/check_docs.py`) and OpenAPI validation.
- `make test` — skeleton tests, including the mutation tests of check_docs.
- `make backtest` — estimator baseline MAPE on the vendored FINAL_TASK results.
- `make db-up` / `make migrate` / `make secret-scan` — dev DB, 마이그레이션 적용, 비밀 패턴 검사(`infra/README.md`). 환경변수 이름: `.env.example`.
