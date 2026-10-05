# infra

Dev stack and CI (owner: infra, CMD-GC11). `docker compose -f infra/docker-compose.yml --env-file .env up db`.

- `make db-up` / `make db-down` — postgres:16 (`.env` 필요, 이름은 `.env.example`). 전체 스택: `docker compose -f infra/docker-compose.yml --env-file .env up` (db, api, worker, web).
- `make migrate` — `backend/migrations/*.sql` 순서대로 적용(`DATABASE_URL`, psql).
- `make secret-scan` — `infra/secret_scan.py`, 비밀 패턴 grep(값은 출력하지 않음). `make check` 에 포함.
- CI: `.github/workflows/ci.yml` — make check, make test, make secret-scan, 마이그레이션 적용.
