# 시각화 계약

사양 3 절의 화면 9 개와 3.1 의 라이브 워크플로 모니터(화면 10). 화면마다 답하는 질문, 차트 형태, 읽는 API 경로와 시리즈, 단위, 출처 표시를 고정한다.

**규칙**

1. 차트는 원본 테이블을 읽지 않는다. 아래 `api:` 줄의 경로(docs/api/openapi.yaml)만 부른다. `scripts/check_docs.py` 가 각 `api:` 경로가 openapi.yaml 에 그 메서드로 있는지 검사한다.
2. 차트 라이브러리: ECharts (ADR-0001). 색 · 모양 토큰은 `frontend/src/lib/chart-theme.ts` 한 곳에.
3. 금액은 API 의 정수 micro-USD 를 화면에서만 USD 로 바꾼다(`$0.0123`, 소수 4 자리, 1 달러 이상이면 2 자리). 토큰은 천 단위 구분 + 축약(`12.3k`, `1.2M`).

## 출처 표시 (모든 화면 공통)

| 출처 | 선 · 면 | 숫자 옆 칩 | 툴팁 |
|---|---|---|---|
| `MEASURED` | 실선, 채움 100 % | `측정` (회색 테두리) | "공급자 usage / CLI 보고값" |
| `CALCULATED` | 실선, 채움 70 % | `계산` | 계산식 이름 + 가격표 버전 |
| `ESTIMATED` | 점선 + P10–P90 띠(투명 25 %) | `추정` (주황) | 근거 N 건, 견적기 버전, 최근 MAPE |
| `SIMULATED` | 파선 + 빗금 띠 | `가정` (보라) | 가정 목록 전체 + 데이터 기준(기간 · 호출 수 · 가격표 버전) |

- 출처가 다른 값을 한 선에 잇지 않는다. 실측 → 예측 이음은 마지막 실측 점에서 선 종류를 바꾼다.
- 비용은 항상 **두 기준을 나란히**: `정가 환산 (list)` 과 `CLI 비용 (cli)`. `cli` 의 `coverage_permille < 1000` 이면 칩에 `부분 n%` 를 붙인다. 값이 null 이면 0 이 아니라 `—`.
- 범위(`Range`)는 P50 을 점/선으로, P10–P90 을 띠/오차 막대로 그린다.

---

## screen: overview — 개요 대시보드

- status: MVP
- question: 이번 기간 토큰 · 비용이 얼마이고, 맞힌 작업 하나에 얼마가 들며, 예산의 몇 %를 썼나?
- chart: 지표 타일 7 개(총 토큰, 비용 list, 비용 cli, 맞힌 작업 수, 맞힌 작업당 비용 list / cli, 예산 사용률) + 일별 추세선(토큰, 비용 두 기준)
- api: `GET /v1/workspaces/{ws}/usage/summary`
- api: `GET /v1/workspaces/{ws}/budgets`
- series: `tiles.*` (Metric), `trend.series[name in (total_tokens, cost_list, cost_cli)]`; 예산 사용률은 `budgets[].used` 중 workspace · month 예산
- units: tokens, microusd, tasks, permille
- provenance: 토큰 MEASURED, 비용 list CALCULATED, cli MEASURED(+ 커버리지), 맞힌 작업당 CALCULATED

## screen: token_mix — 토큰 구성

- status: MVP
- question: 토큰이 입력 · 캐시 읽기 · 캐시 쓰기 · 출력 중 어디에 쓰이고, 모델별로 어떻게 다른가?
- chart: 누적 영역 차트(시간 × 토큰 4 종), 모델별 작은 배수(small multiples) 전환
- api: `GET /v1/workspaces/{ws}/usage/series/tokens`
- series: `series[name in (input, cache_read, cache_write, output)]`, `group_by=model` 이면 이름 접두 `<model>:`
- units: tokens / bucket(hour · day · week)
- provenance: MEASURED (실선 채움)

## screen: call_size — 호출 크기 분포

- status: MVP
- question: 호출당 문맥이 얼마나 크고, 대량 주입(> 5 만) 호출은 어디 있나?
- chart: 로그 2 구간 히스토그램 + 임계 세로선 + 이상치 점(클릭 → 호출 목록)
- api: `GET /v1/workspaces/{ws}/usage/series/call-size`
- api: `GET /v1/workspaces/{ws}/usage/calls`
- series: `bins[]`, `outliers[]`, `threshold`; 상세는 `usage/calls?min_input=<threshold>`
- units: tokens (x), calls (y)
- provenance: `context_tokens` 는 CALCULATED(측정 토큰의 합). 연결된 R1 finding 이 있으면 절감액을 ESTIMATED 칩으로

## screen: node_timeline — 노드 타임라인

- status: later (Run 도메인)
- question: ga 실행에서 각 노드가 언제 시작 · 턴 · 대기 · 은퇴했나?
- chart: 간트 차트, 역할별 레인, 스팬 색 = turn / wait / idle; 실행 중에는 SSE 로 갱신
- api: `GET /v1/workspaces/{ws}/runs/{run}/timeline`
- api: `GET /v1/workspaces/{ws}/runs/{run}/events`
- series: `lanes[].spans[]`, SSE `run_events`
- units: ms (x), tokens(툴팁)
- provenance: MEASURED

## screen: task_flow — 작업 흐름

- status: later (Run 도메인)
- question: 작업이 대기 → 실행 → 판정 → 통합 중 어디서 빠지나?
- chart: 퍼널
- api: `GET /v1/workspaces/{ws}/runs/{run}/flow`
- series: `stages[]` (count, dropped)
- units: tasks
- provenance: MEASURED

## screen: peer_network — 동료 네트워크

- status: later (Run 도메인)
- question: 노드 사이에 메시지가 얼마나 오갔고, π 가중치와 예산 사용은 어떤가?
- chart: 힘 기반 네트워크 그래프(노드 크기 = 토큰, 간선 두께 = 메시지 수, 간선 색 = π)
- api: `GET /v1/workspaces/{ws}/runs/{run}/network`
- series: `nodes[]`, `edges[]`
- units: count, tokens (tokens_est 는 ESTIMATED: bytes/4)
- provenance: 메시지 수 MEASURED, tokens_est ESTIMATED

## screen: verdicts — 판정 결과

- status: later (Run 도메인)
- question: 작업별로 시험이 통과했는지, 변이가 잡혔는지, 원래 있던 실패는 무엇인지?
- chart: 표 + 상태 칩(pass · fail · partial)
- api: `GET /v1/workspaces/{ws}/runs/{run}/verdicts`
- series: `[]` Verdict
- units: count
- provenance: MEASURED (`ga judge` 결과)

## screen: config_compare — 구성 비교

- status: MVP
- question: 구조(A/B/C) · 모델 · 문맥 방식 중 어느 구성이 맞힌 작업당 토큰 · 비용이 가장 낮고 정답률은 어떤가?
- chart: 묶음 막대(맞힌 작업당 비용 list / cli) + 오차 막대(P10–P90) + 정답률 점(보조 축)
- api: `GET /v1/workspaces/{ws}/usage/compare`
- api: `GET /v1/workspaces/{ws}/profile/recommendations`
- series: `groups[].tokens_per_correct`, `cost_list_per_correct`, `cost_cli_per_correct` (Range), `accuracy` (Metric); 추천 배너는 recommendations
- units: tokens, microusd, permille
- provenance: CALCULATED (범위는 작업 간 분포, 추정 아님). 추천 배너는 ESTIMATED. What-if 결과를 겹쳐 그릴 때는 SIMULATED 표기 + 가정 목록

## screen: budget_burn — 예산 소진

- status: MVP
- question: 예산 대비 누적 사용이 어디까지 왔고, 언제 상한에 닿을 것인가?
- chart: 누적 선(list, cli) + 상한 가로선 + 예측 선(P50) 과 구간(P10–P90) + 임계 표시(50 · 80 · 100 %)
- api: `GET /v1/workspaces/{ws}/budgets/{budget}/burn`
- api: `GET /v1/workspaces/{ws}/quota/alerts`
- series: `cumulative.list`, `cumulative.cli`, `projection.p10/p50/p90`, `exhaust_at_*`
- units: microusd (y), 날짜 (x)
- provenance: 누적 list CALCULATED, cli MEASURED, 예측 ESTIMATED (점선 + 띠)

## screen: live_monitor — 라이브 워크플로 모니터

- status: phase 1b (사양 3.1 · 3.1.1, 사용자 추가 요청). 웹 + 데스크톱 셸(ADR-0008), `.ga` 를 읽기만 한다. 조작 없음
- question: 지금 일꾼들이 무엇을 하고 있고, 서로 어떻게 돕고 있으며, 어디서 막혔나?
- chart: 움직이는 장면 하나(Canvas 2D, 어두운 테마). 페이지 · 탭 · 표가 없다. figure(역할 모양) · tile(작업) · 펄스(메시지) · 선 굵기(π) · 고리(결과) · 연료 호와 수평선(토큰 · 비용) · 분위기(속도 · 막힘 · 협업 · 긴장 · 완료). 재생 스크러버는 마우스를 올릴 때만 보인다. 시각 언어는 docs/ui-design.md 6 절, 신호별 대응은 design/encoding.json
- api: `GET /v1/workspaces/{ws}/monitor/sources/{source}/snapshot`
- api: `GET /v1/workspaces/{ws}/monitor/sources/{source}/events`
- api: `GET /v1/workspaces/{ws}/monitor/sources/{source}/recordings/{recording}`
- series: 처음에는 `MonitorSnapshot` (figures · tiles · edges · meters · mood), 그 뒤 SSE `MonitorEvent` (monitor-event/1, `kind` = 아래 신호). 재생은 녹화 JSONL 을 같은 렌더러에 `t` 를 바꿔 가며 넣는다
- signals: `file:queue.added`, `file:pool.live.claimed`, `file:queue.done`, `file:queue.failed`, `file:pool.live.idle`, `file:pool.live.retiring`, `file:pool.round`, `file:node.state.consults`, `file:node.run.cont_open`, `file:node.state.done`, `file:node.pi`, `file:node.budget.grow`, `file:usage.snapshot`, `derived:pace`, `derived:collaboration`, `derived:stall`, `derived:tension`, `derived:all_done` (+ L0 종류 전부: `check_docs.py` 의 목록)
- units: 무대에는 숫자가 없다. 호버 툴팁에만 tokens, microusd, ms(경과), count
- provenance: 무대에는 칩이 없다(글자 최소). 툴팁에서 작은 단어로 보인다.
  - 토큰 · 비용(`run.end` reported) = MEASURED.
  - 메시지 `tokens_est` = ESTIMATED(bytes/4).
  - 경과 시간 = CALCULATED(모니터 관측 시각 기준). ga 0.6 L0 에는 시각이 없다(`at: null`).
  - 턴 진행은 "running (elapsed)" 로만 보인다. turn.started 가 없기 때문이다.

## 보조 화면 (MVP, 사양 3 절 표 밖)

화면 10 개 외에 MVP 흐름에 필요한 화면. 같은 규칙을 따른다.

| 화면 | 읽는 API |
|---|---|
| 업로드 · 수집 진행 | `POST /v1/workspaces/{ws}/uploads`, `GET …/ingest-jobs/{job}/events` (SSE 진행 막대) |
| 절약 진단 | `GET …/advisor/findings`, `GET …/proposals`, `POST …/proposals/{proposal}/decision` |
| 견적 | `POST …/estimates`, `GET …/estimation/accuracy` (자체 MAPE 표시) |
| What-if | `POST …/simulations` |
| 프로필 | `GET/PUT …/profile`, `GET …/profile/stats` |
| 알림 · 감사 로그 | `GET /v1/notifications`, `GET …/audit-log` |
