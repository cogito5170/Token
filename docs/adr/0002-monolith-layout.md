# ADR-0002 Modular monolith 배치

- 상태: 채택
- 결정: 하나의 저장소 · 하나의 백엔드 패키지 `backend/app`, 도메인마다 `app/domains/<domain>/` 패키지 하나(15 개). 각 패키지는 `api.py`(다른 도메인이 부르는 유일한 진입점), `router.py`(FastAPI 경로, 자기 x-domain 경로만), `service.py`, `repo.py`(자기 owned_tables 만 SQL), `models.py`(Pydantic), `tests/`.
- 규칙:
  - 다른 도메인의 `service`/`repo`/`models` import 금지 — `api` 만. `backend/tests/test_boundaries.py` (core-backend 작업)가 import 그래프를 검사한다.
  - 테이블 소유는 domain-model.md 가 원본이고 `app/domains/<d>/__init__.py` 의 `OWNED_TABLES` 와 같아야 한다(skeleton 시험이 검사).
  - 공통 코드는 `app/core` 에만: 설정, DB 풀, 인증 의존성, 이벤트 버스, provenance, 로그 필터.
- 이유: 3–5 개의 병렬 작업 흐름이 서로 덮어쓰지 않으려면 파일 소유가 도메인 경계와 일치해야 한다(docs/ownership.md). 마이크로서비스는 MVP 규모에 비해 운영 비용이 크다. 경계가 지켜지면 나중에 도메인 하나를 떼어 낼 수 있다.
