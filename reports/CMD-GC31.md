```ga
{"schema":"report/2","from":"consulting","handled":[{"id":"CMD-GC31","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc31","sha":"9f43df749bd536555ef92ee86f051d713a0055aa"}],"tests":{"passed":49,"failed":0,"skipped":3},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["backtest --estimator app: tokens MAPE 12.04% < 21.98% baseline, P10-P90 coverage 89.0% (test_beats_baseline_with_coverage)"]},{"id":"D2","state":"met","evidence":["test_few_evidence_widens: n<3 gives P10x0.5, P90x2, evidence_n shown"]},{"id":"D3","state":"met","evidence":["test_featurize_drops_text, test_service_row_has_no_text: description stored as sha256+len only"]}]}
```

## 한 일
`backend/app/domains/estimation/` 에 견적기 구현: `features.py`(특징 · 거리, 설명은 길이+해시만), `estimator.py`(k=15 최근접 근거, 가중 P10/P50/P90, 라플라스 성공확률, λ=n_u/(n_u+10) 혼합, 근거 3건 미만 시 범위 확대), `prior.py`(fixtures/final_task 전역 사전, void 제외), `outcomes.py`(ape ‰, 포함 여부, MAPE · 포함률), `service.py`/`api.py`(usage.api.tasks 로 사용자 근거). `scripts/backtest_estimator.py` 에 `--estimator app` 추가(평가 대상 run 을 뺀 leave-one-out, 기준선보다 나쁘면 종료코드 2).

## 결과 (FINAL_TASK LOO, 100 run)
| 양 | 기준선 MAPE / 포함률 | app MAPE / 포함률 |
|---|---|---|
| 토큰 | 21.98% / 64.0% | **12.04% / 89.0%** |
| 비용 list | 92.68% / 65.0% | 104.52% / 88.0% |
| 비용 cli | - | 65.48% / 87.0% |

FINAL_TASK 의 task_kind = task id(T1..T5), structure = arm, context_mode = mode 로 매핑.

## 시험
estimation 14개(leakage 시험 포함: 평가 대상 run 이 자기 근거에 있으면 실패), make test 49 통과 · 3 skip(런타임 의존성), make check 0 문제. origin/claude/gracious-meitner-vp49xe 병합 후 재실행.

## 열린 문제
- list 비용 MAPE 는 기준선보다 나쁘다(104.5% vs 92.7%): bulk 모드 2자릿수 배 차이 때문에 P50 이 가중 평균 쪽으로 끌린다. 완료 조건은 토큰만 요구. 개선하려면 context_mode 불일치 가중을 키우는 방안.
- HTTP 라우트 (/estimates*, /estimation/accuracy)와 PG 저장소(estimates 등 테이블)는 만들지 않았다: 서비스는 메모리 저장. 후속 항목 필요.
- 지속 시간(duration_ms)은 fixture 에 없어 전역 사전 범위가 비어 있다. 추천 구성(1.2 절 7단계)은 미구현.

## baseline 요청
- 라우터/PG 저장소를 만들 후속 항목(estimation 의 router.py · pg_store.py 와 openapi 연결) 등록.
