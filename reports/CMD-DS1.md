```ga
{"schema":"report/2","from":"design","handled":[{"id":"CMD-DS1","rev_seen":1,"status":"done"}],"commits":[],"tests":{"passed":7,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["design/tests/tokens/test_tokens.py: text pairs >=4.5 and UI pairs >=3 in light+dark","design/tests/tokens/test_tokens.py::test_series_luminance_gap >=0.08","design/tests/tokens/test_tokens.py::test_no_red_green","scripts/check_docs.py: 0 problem(s)"]}]}
```

## 한 일
- `design/tokens.json` 은 이미 있었다. 시리즈 색을 바꿔 두 테마 모두 시리즈 ↔ bg/surface 대비 ≥ 3:1 과 시리즈 간 상대 휘도 차 ≥ 0.08 을 만족시켰다(light 휘도 .021/.103/.188/.274, dark .145/.301/.450/.600). 파랑/주황만 쓴다.
- `contrast_pairs` 를 확장: text/muted/accent/warm 대 bg·surface(4.5), focus(3.0), border(1.3), 두 테마 모두.
- `design/README.md`(frontend 용 토큰 설명, CSS 변수 규칙), `design/__init__.py`, `design/tests/__init__.py`, `design/tests/tokens/` 테스트 7 개 추가.

## 파일
design/tokens.json, design/README.md, design/__init__.py, design/tests/__init__.py, design/tests/tokens/{__init__,test_tokens}.py, reports/CMD-DS1.md

## 테스트
item check(unittest 7), `make check`, `make test`, `scripts/check_docs.py` 모두 통과. 스키마 테스트(DB)는 이 항목과 무관해 돌리지 않음.

## 열린 문제 / baseline 요청
- 없음. 시리즈 계열 색 변경이라 dark 의 cache_read 가 이전보다 밝아졌다. 색 값은 frontend 가 토큰으로만 읽으므로 영향 없음.

## 다음 세션 참고
- 시리즈는 차트의 UI 쌍으로 취급해 bg/surface 대비 ≥ 3 을 테스트가 강제한다. 값을 바꾸면 README 의 명령으로 재검증.
