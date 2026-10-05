"""Advisor domain (advisor). Skeleton only (CMD-GC0); see docs/domain-model.md.

낭비 규칙 7 종(consulting.md 3 절) 실행 → 발견(finding, 근거 호출 id 와 절감 추정) → Proposal 생성. Proposal 의 상태기계(proposed → accepted/rejected → applied | expired)와 결정 기록. 다른 출처(simulation, 나중 run 노드)의 Proposal 도 이 인터페이스로만 들어온다.
"""
DOMAIN = "advisor"
MVP = True
OWNED_TABLES = ('advisor_rules', 'advisor_findings', 'proposals', 'proposal_decisions',)
