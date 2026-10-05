"""Ingestion domain (ingestion). Skeleton only (CMD-GC0); see docs/domain-model.md.

수집 작업 상태기계(queued → parsing → normalizing → loading → analyzing → done | failed), 형식 감지, 기존 파서 호출(l0-telemetry · rlo), 비밀값 제거, `UsageCall` 정규화, 중복 제거 키 계산, 진행 이벤트(SSE 원천), 거부 행 기록.
"""
DOMAIN = "ingestion"
MVP = True
OWNED_TABLES = ('ingest_jobs', 'ingest_job_events', 'ingest_rejects',)
