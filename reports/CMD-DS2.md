```ga
{"schema":"report/2","from":"design","handled":[{"id":"CMD-DS2","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/ds2","sha":"e85daaf79d12b2ecb67b9f6b647f2a4c5a472b7c"},{"repo":"cogito5170/Token","branch":"claude/ds2","sha":"da4c1fbe93033e024265e631f490784c75ccdce9"},{"repo":"cogito5170/Token","branch":"claude/ds2","sha":"9ac3583f3f644d10a7858dcad1c96ab60779d838"}],"tests":{"passed":67,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["design/encoding.json: 49 signals = every L0 kind (L0_KINDS_GA + L0_KINDS_CATALOG) + 18 live_monitor file/derived signals","design/tests/encoding/test_encoding.py Coverage"]},{"id":"D2","state":"met","evidence":["every ga-emitted signal has visual, motion, duration, reduced_motion (no movement terms) and a shape/size non-color cue","design/tests/encoding/test_encoding.py GaEmitted, Motion"]},{"id":"D3","state":"met","evidence":["stage words only build/wait/talk/test/done, test reserved, glossary_banned_on_stage extended, no emoji","design/tests/encoding/test_encoding.py Words"]},{"id":"D4","state":"met","evidence":["encoding.json figures (6 role shapes, states = data-model 7.3, rings, edge 1-6 px), tiles, moods (rules, priority, combine), stage, limits; design/motion.md","design/tests/encoding/test_encoding.py FiguresAndMoods"]},{"id":"D5","state":"met","evidence":["python3 -m unittest discover -s design/tests/encoding -t . -> 26 OK","make check 0 problems","make test with GC_SCHEMA_TEST_DSN (local PostgreSQL 16) -> 31 + 4 OK","design/tests/tokens 6 OK"]}]}
```

# CMD-DS2 보고 (design)

## 한 일

- `design/encoding.json` 을 완성했다. 신호 이름(MonitorEvent `kind`)은 그대로 두었으므로 CMD-RN1 과 맞는다.
  - 모든 신호에 `target`(figure · tile · edge · meter · stage · none)과 `duration`(`durations_ms` 의 키)을 더했다.
  - ga 0.6 이 내는 신호 중 움직임 줄이기 · 색 아닌 단서가 "none" / "n/a" 이던 것(`file:pool.round`, `derived:pace`)을 실제 형태로 바꿨다(rim 눈금 수, 먼지 밀도). reduced_motion 글에서 이동 말(travel, orbit, sweep …)을 모두 뺐다.
  - 새 구역: `words_reserved`(test 예약), `word_style`, `durations_ms`(tokens.json 과 같은 값 + `travel` 800), `reduced_motion`, `stage`(띠 · 선반 · 쉼 테두리 · 수평선), `figures`(역할 모양 6 개와 7 번째부터 안쪽 홈, 상태별 밝기 = data-model 7.3 의 상태, 고리 모양, 은퇴 표시, 선 굵기 1–6 px), `tiles`, `moods`(조건 · 템포 배수 · 밝기 · 우선순위 · 합치는 규칙), `limits`.
  - `glossary_banned_on_stage` 를 넓혔다(tokens, session, item, turn, role, peer, pool, budget, cost, model …).
- `design/motion.md` 를 한국어로 다시 썼다: 시간 · 무대 · 모양 · 분위기 표 · 글자 · 움직임 줄이기 · 한계.
- `design/tests/encoding/test_encoding.py`(26 시험): 목록은 `scripts/check_docs.py` 의 `L0_KINDS*` · `screen_signals` 를 읽어 쓰므로 핀이 바뀌면 함께 따라간다.

## 바꾼 파일

`design/encoding.json`, `design/motion.md`, `design/tests/encoding/__init__.py`, `design/tests/encoding/test_encoding.py`, `reports/CMD-DS2.md`

## 시험

- `python3 -m unittest discover -s design/tests/encoding -t .` → 26 OK
- `make check` → 0 problem, openapi 0 problems
- `GC_SCHEMA_TEST_DSN=postgresql://postgres@localhost:5433/postgres make test` → 31 OK + backend 4 OK (컨테이너 안 PostgreSQL 16)
- `design/tests/tokens` → 6 OK
- origin/claude/gracious-meitner-vp49xe 를 merge 한 뒤 다시 돌렸다.

## 남은 문제

- `test` 단어는 ga 가 검사 이벤트를 낼 때까지 어떤 신호도 쓰지 않는다.
- `durations_ms.travel`(800 ms)은 tokens.json `motion.duration_ms` 에 없다. 이 작업은 tokens.json 을 소유하지 않아 encoding.json 에만 두었다.

## baseline 요청

- 다음 design 작업에서 `design/tokens.json` `motion.duration_ms` 에 `travel: 800` 을 더해 두 파일을 하나로 맞추기를 제안한다.
- `design/README.md` 는 토큰만 설명한다. encoding.json · motion.md 안내 한 줄을 더하는 것을 제안한다(이 작업의 파일 밖).

## 다음 세션이 알 것

- CMD-DS3: golden 은 `figures.states` · `figures.rings` · `tiles.shelves` · `moods.rules` 의 이름을 그대로 쓰면 된다. 무대 단어는 `word` 값(또는 `moods.rules[*].word`)뿐이다.
- CMD-FE2: 시간은 `durations_ms[signal.duration]`, 움직임 줄이기는 `reduced_motion` 글 + `reduced_motion.max_fade_ms`. 모양 · 색 · 시간을 새로 만들지 않는다.
