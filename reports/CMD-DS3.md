```ga
{"schema":"report/2","from":"design","handled":[{"id":"CMD-DS3","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/ds3","sha":"8dd1826c9a5d8da04b8a32bfc3a8ab054a172048"}],"tests":{"passed":85,"failed":0,"skipped":3},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["design/golden/reference.py","python3 -m design.golden.reference --check -> exit 0","design/tests/golden/test_golden.py::Reproducible.test_every_golden_regenerates_byte_identically"]},{"id":"D2","state":"met","evidence":["design/tests/golden/test_golden.py::Words.test_only_allowed_words","python3 -m unittest discover -s design/tests/golden -t . -> 7 OK"]},{"id":"D3","state":"met","evidence":["design/tokens.json motion.duration_ms.travel=800","design/README.md","design/tests/tokens -> 7 OK","design/tests/encoding -> 26 OK"]}]}
```

# CMD-DS3 보고 (design)

## 한 일
- `design/golden/reference.py`: 표준 라이브러리만 쓰는 순수 함수 `scene(events, t_ms, encoding)`. MonitorEvent 녹화에서 장면의 뜻을 만든다:
  figure 상태 · 밝기 · 모양(역할 순서) · 고리 · tether · 은퇴 표시 · 단어, 모든 tile 의 선반 · 부모, 선의 pi · 굵기(1–6 px, 반올림) · 메시지 수,
  분위기(활성 분위기, 템포 `tempo_permille` 정수, 밝기 차), 무대 단어, 보이는 단어 목록.
  `python3 -m design.golden.reference` 로 쓰고 `--check` 로 비교한다.
- `design/golden/t{00000,01000,02000,03000,04000,05000,07000,08000,09000,12000}.json`: fixture script 의 각 단계 + 단어가 사라진 뒤(12 s). 각 파일에 녹화 sha256.
- `design/tests/golden/test_golden.py` (7 개): 바이트 동일 재생성, 순수성(이벤트 순서 무관), 녹화 해시, 허용 단어만(예약된 `test` 제외), 금지어 없음, encoding 값 범위, 이야기 확인.
- CMD-DS2 요청: `design/tokens.json` motion.duration_ms 에 `travel: 800`, `design/README.md` 에 encoding.json · motion.md 안내 한 줄.

## 바꾼 파일
design/golden/** (새로), design/tests/golden/** (새로), design/tokens.json, design/README.md, design/tests/tokens/test_tokens.py.

## 시험
- `python3 -m unittest discover -s design/tests/golden -t .` → 7 OK (done_when)
- design/tests/tokens 7 OK, design/tests/encoding 26 OK
- `make check` 0 문제, `make test` 48 실행 · 3 건너뜀(GC_SCHEMA_TEST_DSN 없음 등 런타임 의존) · 실패 0
- origin/claude/gracious-meitner-vp49xe 병합 뒤 다시 돌려 모두 녹색.

## 열린 문제
- `design/tests/tokens/test_tokens.py` 가 duration 키 집합을 고정해서 `travel` 추가로 깨졌다. 같은 design 소유(design/**)라 한 줄 고쳤다(집합에 travel 추가). 이 항목의 files 밖이므로 알린다.
- 해석으로 정한 규칙(README 에 적음): figure 단어 = 그 figure 대상 신호의 마지막 단어, 2 초 유지. tile 신호 단어는 그 tile 을 든 figure 에 붙인다.
  peers 가 빈 consults 는 `wait` 를 보이지 않는다. 버림 표시는 1 초 `dropped_marks`. 템포는 소수 대신 permille 정수.
- figure 크기 · 연료 호(tokens) 는 golden 에 넣지 않았다(목표 범위 밖, 녹화의 budget.grow 토큰이 누적인지 불분명).

## baseline 요청
- 위 test_tokens.py 한 줄 변경을 이 항목 소유로 인정해 주기.
- CMD-FE2 는 `design/golden/t*.json` 의 키 이름(`tempo_permille`, `dropped_marks`, `stage_word`, `words`) 을 그대로 비교 대상으로 쓰면 된다.

## 다음 세션이 알아야 할 것
- 녹화가 바뀌면 `python3 -m design.golden.reference` 로 다시 만들고 커밋한다(해시가 파일에 있어 시험이 알려 준다).
- t 는 첫 이벤트 observed_at 기준 ms, observed_at <= t 인 이벤트만 반영한다.
