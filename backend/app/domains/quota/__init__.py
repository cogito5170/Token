"""Quota domain (quota). Skeleton only (CMD-GC0); see docs/domain-model.md.

예산(작업 · 일 · 월 · 워크스페이스/프로젝트 범위, 기준 `list` | `cli`), 두 기준 사용률, 소진 예측(선형 + 구간), 임계(50 · 80 · 100 %) 경보 생성.
"""
DOMAIN = "quota"
MVP = True
OWNED_TABLES = ('budgets', 'budget_alerts',)
