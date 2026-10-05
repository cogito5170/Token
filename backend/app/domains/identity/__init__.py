"""Identity domain (identity). Skeleton only (CMD-GC0); see docs/domain-model.md.

계정 생성, 로그인, 액세스 토큰(JWT, 15 분) 발급, 리프레시 토큰(30 일, 회전) 관리, Argon2id 비밀번호 해시.
"""
DOMAIN = "identity"
MVP = True
OWNED_TABLES = ('users', 'refresh_tokens',)
