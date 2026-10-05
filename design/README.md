# 디자인 토큰 (frontend 용)

원본은 `design/tokens.json` 하나다(소유: design). 색 · 크기 · 시간을 다른 곳에 직접 쓰지 않는다. 계약 문서는 `docs/ui-design.md` 1–3 절.

## 구조

| 키 | 내용 | CSS 변수 규칙 |
|---|---|---|
| `font.sans` / `font.mono` | IBM Plex Sans KR / IBM Plex Mono (self-host, ADR-0009) | `--gc-font-sans`, `--gc-font-mono` |
| `font.numeric` | 모든 숫자에 `font-variant-numeric: tabular-nums` | — |
| `type_scale_px` | 12 · 14 · 16 · 20 · 24 · 28(title) · 32(kpi) | `--gc-text-<이름>` |
| `line_height`, `weight` | 줄 높이 · 글자 굵기 | `--gc-leading-*`, `--gc-weight-*` |
| `space_px` | 4 의 배수(0–64) | `--gc-space-<n>` |
| `radius_px` | sm 4 · md 8 · lg 12 · full | `--gc-radius-*` |
| `elevation` | 0 · 1 · 2 단계만 | `--gc-elevation-*` |
| `layout` | 본문 최대 폭 · 내비 폭 · 중단점 | `--gc-layout-*` |
| `themes.light` / `themes.dark` | bg, surface, text, muted, border, accent, warm, focus, `series`, `band_opacity` | `--gc-color-<이름>`, `--gc-series-<이름>` (테마별로 `[data-theme]` 아래에 선언) |
| `provenance` | 출처 칩 4 종: 칩 모양 · 선 모양 · 한글 라벨 | 색이 아니라 선 모양(solid/outlined/dashed/dotted)으로 구분 |
| `motion` | 지속 시간 · easing · reduced-motion 규칙 | `--gc-duration-*`, `--gc-ease-*` |

## 규칙

- 강조색은 화면당 하나(accent). `warm` 은 추정 · 긴장 신호에만 쓴다.
- 계열(`series`)은 파랑 / 주황뿐이고 빨강 · 초록 쌍은 없다. 계열끼리 상대 휘도 차 ≥ 0.08.
- 대비: 본문 쌍(text, muted, accent, warm 대 bg, surface)은 두 테마 모두 ≥ 4.5:1. UI 쌍(focus, accent, warm, 계열 대 bg, surface)은 ≥ 3:1. `contrast_pairs` 에 선언된 쌍은 `scripts/check_docs.py` 가, 전체는 `design/tests/tokens` 가 검사한다.
- 토큰 값을 바꾸면 `python3 -m unittest discover -s design/tests/tokens -t .` 와 `python3 scripts/check_docs.py` 를 돌린다.
- 움직임 줄이기: `prefers-reduced-motion: reduce` 이면 지속 시간 0(불투명도 페이드 ≤ 120 ms 예외), 이동 · 숨쉬기 · 입자 없음.
