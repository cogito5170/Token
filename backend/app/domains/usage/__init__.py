"""Usage domain (usage). Skeleton only (CMD-GC0); see docs/domain-model.md.

정규화 사용 모델의 저장과 읽기. 호출 · 세션 · 작업 · 모델 카탈로그 · 정가표 · 일별 집계. 비용 계산(정가 환산, CALCULATED). 차트용 시계열 · 분포 · 비교 쿼리.
"""
DOMAIN = "usage"
MVP = True
OWNED_TABLES = ('models', 'model_prices', 'usage_sessions', 'usage_tasks', 'usage_calls', 'usage_daily',)
