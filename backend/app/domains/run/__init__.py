"""Run (나중) domain (run). Skeleton only (CMD-GC0); see docs/domain-model.md.

플랫폼 안 ga 0.6 실행(노드 풀), 노드 타임라인, 동료 메시지 · π 가중치, 판정 결과, 작업 흐름 퍼널, 실행 SSE. MVP 에서는 스키마 · API 설계만 있고 구현하지 않는다.
"""
DOMAIN = "run"
MVP = False
OWNED_TABLES = ('runs', 'run_nodes', 'run_events', 'run_messages', 'run_verdicts',)
