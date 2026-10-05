"""Integration domain (integration). Provider keys (CMD-GC18, ADR-0007); see docs/domain-model.md.

외부 연동(GitHub · Slack, 나중) 설정, 공급자 키 봉투 암호화 보관(ADR-0007). 키는 지문(fingerprint)과 끝 4 자만 돌려준다.
통합(GitHub · Slack) 은 읽기 전용 목록만 있다: 연결 · 생성 경로는 계약에 없다(나중).
"""
DOMAIN = "integration"
MVP = False
OWNED_TABLES = ('integrations', 'provider_credentials',)
