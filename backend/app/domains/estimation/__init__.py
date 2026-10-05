"""Estimation domain (estimation). Skeleton only (CMD-GC0); see docs/domain-model.md.

실행 전 견적. 입력 특징화, 근거 집합(유사 과거 작업 N 건) 선택, P10/P50/P90(토큰 입력 · 캐시 · 출력, 비용 두 기준, 호출 수, 시간)과 성공 확률, 실제값과 비교한 오차(MAPE) 기록. 전역 사전(FINAL_TASK)과 사용자별 보정.
"""
DOMAIN = "estimation"
MVP = True
OWNED_TABLES = ('estimates', 'estimate_evidence', 'estimate_outcomes', 'estimator_models',)
