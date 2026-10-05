# ADR-0007 공급자 키 보관

- 상태: 채택 (MVP 에서는 스키마 · API 계약만, 키를 쓰는 기능은 나중)
- 결정: 봉투 암호화. 키마다 무작위 DEK 로 AES-256-GCM, DEK 는 KEK 로 감싸 저장(`wrapped_dek`, `kek_id`). KEK 는 개발에서 환경 변수, 운영에서 KMS. API 는 쓰기 전용이며 `CredentialRef`(fingerprint, last4)만 돌려준다. 평문은 `integration.api.use_credential` 컨텍스트 안에서만.
- 대안: (a) 키를 아예 받지 않고 사용자 실행기가 L0 만 올리는 방식 — 사양 원칙 4 가 허용하며 기본 권장 경로로 문서화한다. (b) DB 열 암호화(pgcrypto) — DB 권한만으로 복호화되므로 기각.
- 결과: KEK 회전은 `wrapped_dek` 만 다시 감싸면 된다. 키 문자열이 응답 · 로그 · 감사에 없는지 자동 시험(security.md 2 절).
