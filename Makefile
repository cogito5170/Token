PY ?= python3
COMPOSE ?= docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: dev dev-down dev-env dev-migrate test check backtest schema-check db-up db-down migrate secret-scan

dev-env:         ## create ./.env with generated dev-only values (refuses to overwrite)
	@test -f .env || $(PY) scripts/dev_env.py

dev: dev-env     ## local stack: db, api, worker, web at http://localhost:3000
	$(COMPOSE) up -d --wait db
	$(MAKE) dev-migrate
	$(COMPOSE) up -d api worker web
	@echo "web http://localhost:3000   api http://localhost:8000/healthz   (first start installs packages; docker compose logs -f)"

dev-migrate:     ## apply backend/migrations/*.sql inside the db container when the schema is missing
	@$(COMPOSE) exec -T db psql -U gaconsole -d gaconsole -qAt -c 'select 1 from users limit 1' >/dev/null 2>&1 || { \
		for f in $$(ls backend/migrations/*.sql | sort); do echo "apply $$f"; $(COMPOSE) exec -T db psql -U gaconsole -d gaconsole -v ON_ERROR_STOP=1 -q < $$f || exit 1; done; }

dev-down:        ## stop the local stack (data volume kept)
	$(COMPOSE) down

test:            ## unit tests (runner: unittest)
	$(PY) -m unittest discover -s tests -t .
	cd backend && $(PY) -m unittest discover -s tests -t .
	$(PY) -m unittest discover -s infra/tests -t .
	@if command -v node >/dev/null 2>&1; then \
		cd frontend && { [ -d node_modules ] || npm ci; } && npx vitest run; \
	else echo "SKIP frontend unit tests: node is not installed"; fi

check:           ## contract checks + secret grep
	$(PY) scripts/check_docs.py
	$(PY) scripts/validate_openapi.py
	$(PY) infra/secret_scan.py

secret-scan:     ## secret-pattern grep over the tree
	$(PY) infra/secret_scan.py

backtest:
	$(PY) scripts/backtest_estimator.py

db-up:           ## start postgres:16 (needs .env, see .env.example)
	$(COMPOSE) up -d --wait db

db-down:
	$(COMPOSE) down

migrate:         ## apply backend/migrations/*.sql in order (needs psql; DATABASE_URL)
	@test -n "$$DATABASE_URL" || { echo "DATABASE_URL is not set"; exit 1; }
	@for f in $$(ls backend/migrations/*.sql | sort); do echo "apply $$f"; psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -qf $$f || exit 1; done

schema-check:    ## apply docs/schema.sql to a throwaway database (needs GC_SCHEMA_TEST_DSN)
	$(PY) -m unittest tests.test_schema
