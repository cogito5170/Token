"""Profile domain (profile). Skeleton only (CMD-GC0); see docs/domain-model.md.

개인 프로필(예산, 품질 하한, 선호 모델 · 공급자, 과금 방식, 팀 규모), 사용자별 통계(작업 종류 × 모델 × 구조별 맞힌 작업당 토큰 · 성공률 = 개인 라우터 · 견적 통계), 맞춤 추천.
"""
DOMAIN = "profile"
MVP = True
OWNED_TABLES = ('profiles', 'personal_stats', 'recommendations',)
