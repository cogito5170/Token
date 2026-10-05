# ADR-0001 기술 스택

- 상태: 채택 (CMD-GC0)
- 결정: 백엔드 Python 3.12 + FastAPI + Pydantic v2 + psycopg 3 (SQL 직접, ORM 없음), 프런트엔드 Next.js(TypeScript, App Router) + **ECharts**, 실시간 SSE, 수치는 정수(토큰 bigint, 금액 micro-USD, 비율 ‰).
- 이유:
  - ga-sdk · l0-telemetry · rlo 가 Python(≥3.10)이라 같은 프로세스에서 라이브러리로 부를 수 있다(파서 재사용 조건).
  - SQL 직접: 시계열 집계 쿼리가 핵심이고 스키마가 계약(docs/schema.sql)이므로 ORM 매핑 층이 이득보다 비용이 크다.
  - ECharts vs Recharts: 간트(노드 타임라인), 네트워크 그래프(동료 네트워크), 띠 + 오차 막대, 대량 점(호출 크기)을 하나의 라이브러리로 그릴 수 있는 것은 ECharts 다. Recharts 는 간트 · 네트워크가 없다.
  - SSE vs WebSocket: 흐름이 서버 → 브라우저 한 방향이고, `Last-Event-ID` 재개가 표준이다.
  - 정수: 부동소수 금액의 합산 오차를 없애고, FINAL_TASK 의 $0.0005 호출도 정확히 담는다(호출 행은 nano-USD).
- 결과: 프런트엔드는 openapi.yaml 에서 TypeScript 타입을 생성한다(`openapi-typescript`). 백엔드 응답 모델도 같은 스키마에서 검사한다.
