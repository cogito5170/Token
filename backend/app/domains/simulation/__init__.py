"""Simulation domain (simulation). Skeleton only (CMD-GC0); see docs/domain-model.md.

What-if. 가정(모델 교체, 문맥 상한, 노드 수, 캐시 고정)을 받아 과거 호출을 다시 계산하고 범위로 돌려준다. 모든 결과에 가정 목록과 데이터 기준(기간, 호출 수, 가격표 버전)을 저장.
"""
DOMAIN = "simulation"
MVP = True
OWNED_TABLES = ('simulations',)
