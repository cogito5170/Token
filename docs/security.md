# 보안 · 안전

사양 6 절(설계 원칙 1 · 4 · 6)과 CMD-GC0 S4 를 구현 규칙으로 옮긴다.

## 1. 위협 모델 (요약)

| 자산 | 위협 | 대책 |
|---|---|---|
| 공급자 키 | 로그 · 응답 · 오류 · 백업 유출 | 봉투 암호화(ADR-0007), 쓰기 전용 API, 로그 필터, 시험 |
| 업로드 기록 | 프롬프트 · 코드 · 비밀값 노출 | 본문 기본 미저장, 비밀값 제거, 원본 보존 기한 후 삭제 |
| 계정 | 비밀번호 추측 · 토큰 탈취 | Argon2id, 로그인 속도 제한, 짧은 JWT + 회전 리프레시(재사용 감지) |
| 워크스페이스 경계 | 다른 워크스페이스 데이터 읽기 | 모든 경로 `require_member`, 쿼리에 `workspace_id` 필수, 404 로 존재 숨김, 교차 시험 |
| 설정 · 예산 · 저장소 | AI 제안이 사람 확인 없이 적용 | Proposal 게이트(4 절) |
| 감사 로그 | 변조 | 추가 전용 트리거, 앱 DB 역할에 UPDATE/DELETE 권한 없음 |

## 2. 공급자 키

- 저장: `integration.provider_credentials` — AES-256-GCM 으로 암호화한 `ciphertext`, 키마다 새 DEK, DEK 는 KEK 로 감싸 `wrapped_dek`. KEK 는 환경 변수 `GC_KEK_<id>` (개발) 또는 KMS (운영)에만 있다. DB 백업만으로는 복호화할 수 없다.
- API: `POST …/provider-credentials` 는 비밀값을 받고 `CredentialRef {id, provider, fingerprint, last4, created_at}` 만 돌려준다. 어떤 GET 도 비밀값을 돌려주지 않는다(스키마에 필드가 없다).
- 사용: `integration.api.use_credential(ref)` 컨텍스트 안에서만 메모리에 평문이 있다. 문자열을 로그 · 예외 · 이벤트 · 감사 detail 에 넣지 않는다.
- 로그 필터: `app/core/logging.py` 의 필터가 data-model.md 4.1 의 비밀값 패턴을 모든 로그 레코드에서 `[REDACTED]` 로 바꾼다. 요청 본문은 로그에 남기지 않는다.
- 화면: 키 입력 필드는 제출 뒤 비운다. 목록에는 `provider · ••••last4 · 등록일` 만.
- 대안(사양 원칙 4): 사용자 실행기 — 키를 콘솔에 두지 않고 사용자 쪽 실행기가 L0 만 올린다(나중, `sources.kind='ga_runner'`).
- 시험(roadmap CMD-GC12, CMD-GC17): 키를 등록한 뒤 모든 API 응답 · 로그 캡처 · 감사 행에 키 문자열이 없는지 확인.

## 3. 사용 기록 데이터

- 기본: 프롬프트 · 코드 · 도구 출력 본문은 저장하지 않는다. 토큰 수 · 메타데이터 · 해시만.
- `profiles.store_bodies = true` 일 때만 본문을 객체 저장소에 두며, 저장 전에 비밀값 제거(data-model.md 4.1).
- 업로드 원본: `uploads.purge_after` (기본 7 일) 뒤 삭제, 수집 실패 시에도 같은 기한.
- `ingest_rejects` 에는 줄 번호와 오류 코드만, 원문 줄은 없다.
- 해시: HMAC(워크스페이스 파생 키). 다른 워크스페이스 사이에서 해시를 비교할 수 없다.

## 4. Proposal 게이트 (AI 는 결정권자가 아니다)

```
advisor finding / simulation / recommendation / (나중) run 노드
    └─► advisor.submit_proposal  → proposals(state=proposed)            [audit: proposal.create]
          └─► 사용자: accept | reject                                     [audit: proposal.accept|reject]
                └─► 사용자: apply + confirm=true
                      1. 정책 검사: kind 별 허용(워크스페이스 역할 ≥ developer, repo_change · budget_change 는 admin)
                      2. quota.check(ws, scope, 예상 추가 비용) — 상한을 넘으면 blocked
                      3. 사용자 확인 플래그(confirm) 확인
                      4. 실행: 설정 · 템플릿 내보내기 파일 생성 또는 예산 변경 (MVP 에서 저장소 변경은 하지 않는다)
                      → state=applied | blocked(blocked_reason)                [audit: proposal.apply|proposal.blocked]
```

- MVP 의 "적용"은 내보내기(설정 · 템플릿 파일)와 플랫폼 안 설정(예산 · 라우터 단계 표시)뿐이다. 사용자 저장소 · 외부 시스템을 바꾸지 않는다.
- 나중의 run: 실행 시작 자체가 Proposal(`kind=repo_change` 또는 비용 큰 실행) 승인 뒤에만, push · 의존성 변경은 사양 5 절 승인 게이트.
- `proposal_decisions` 와 `audit_log` 두 곳에 남긴다(앞은 도메인 상태, 뒤는 감사).

## 5. 감사 로그

기록하는 action (최소): `auth.login`, `auth.login_failed`, `auth.refresh_reuse`, `upload.create`, `ingest.finished`, `budget.create|update|archive`, `proposal.create|accept|reject|apply|blocked`, `credential.store|revoke`, `member.add|remove`, `profile.update`, `report.export`, (나중) `run.start|stop`. detail 에는 id · 수치만, 비밀값 · 본문 없음. 조회는 admin 만.

## 6. 인증 (ADR-0006)

- 비밀번호: Argon2id (`argon2-cffi`, m=64 MiB, t=3, p=1), 최소 12 자, 흔한 비밀번호 목록 거부.
- 액세스 JWT: HS256 (`GC_JWT_SECRET`, 환경 변수), 15 분, `sub`, `iat`, `exp`, `jti`.
- 리프레시: 불투명 256-bit, DB 에는 sha256 만, 30 일, 사용마다 회전. 회전된 토큰 재사용 → 그 family 전체 폐기 + `auth.refresh_reuse` 감사.
- 로그인 속도 제한: IP + 이메일 기준 10 회/15 분.
- CORS: 프런트엔드 출처만. CSRF: 리프레시 쿠키는 SameSite=Strict, 상태 변경 API 는 Bearer 헤더 필요.

## 7. 설정과 비밀

- 설정은 환경 변수 이름만 코드에 있다. 저장소에는 `.env.example` (값 없음)만 있다.
- 비밀 환경 변수: `GC_JWT_SECRET`, `GC_KEK_<id>`, `TELEMETRY_HASH_KEY`, `DATABASE_URL`. 로그 시작 시 설정 덤프에서 제외.
- CI 는 `git grep` 으로 키 모양 문자열을 검사한다(roadmap infra 작업).
