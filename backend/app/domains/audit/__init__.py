"""Audit domain (audit). Skeleton only (CMD-GC0); see docs/domain-model.md.

추가 전용 감사 로그. 누가 · 언제 · 무엇을(로그인, 업로드, Proposal 결정 · 적용, 예산 변경, 키 등록 · 삭제, (나중) 실행 시작 · 정지).
"""
DOMAIN = "audit"
MVP = True
OWNED_TABLES = ('audit_log',)
