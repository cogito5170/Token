"""Workspace domain (workspace). Skeleton only (CMD-GC0); see docs/domain-model.md.

워크스페이스 · 구성원 · 역할(admin · developer · viewer) · 프로젝트. 모든 데이터 접근의 범위 검사(`ws` 경로 인자).
"""
DOMAIN = "workspace"
MVP = True
OWNED_TABLES = ('workspaces', 'workspace_members', 'projects',)
