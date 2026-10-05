"""Integration domain (integration). Skeleton only (CMD-GC0); see docs/domain-model.md.

외부 연동(GitHub · Slack, 나중) 설정, 공급자 키 봉투 암호화 보관(ADR-0007). 키는 지문(fingerprint)과 끝 4 자만 돌려준다.
"""
DOMAIN = "integration"
MVP = False
OWNED_TABLES = ('integrations', 'provider_credentials',)
