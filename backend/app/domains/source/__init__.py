"""Source domain (source). Skeleton only (CMD-GC0); see docs/domain-model.md.

기록 출처 등록(업로드 · 나중의 공급자 연결), 업로드 파일 메타데이터(크기, sha256, 감지 형식, 저장 경로). 원본 파일은 객체 저장소에 두고 보존 기간 뒤 지운다.
"""
DOMAIN = "source"
MVP = True
OWNED_TABLES = ('sources', 'uploads',)
