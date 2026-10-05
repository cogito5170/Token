```ga
{"schema":"report/2","from":"ingestion-analytics","handled":[{"id":"CMD-GC23","rev_seen":1,"status":"partial"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc23","sha":"a1af275da84c2fb4024b97173aed5f4dd18167b5"}],"tests":{"passed":8,"failed":0,"skipped":4},"change_size":"component","items":[{"id":"D1","state":"unverified","evidence":["export CSV fixtures exist but their tests skip: l0-telemetry not installable here","claude_code/ga_l0 mapping tested only against stubbed parsers"]},{"id":"D2","state":"met","evidence":["NoOwnParserTests"]},{"id":"D3","state":"met","evidence":["ScrubTests.test_every_pattern_is_removed"]},{"id":"D4","state":"met","evidence":["BodyTests"]}]}
```

## 블로커
`python3 -m venv /tmp/v && /tmp/v/bin/pip install "l0-telemetry @ git+https://github.com/cogito5170/Telemetry@f6c7ae26d336965d3558092517e97d37d222c4ea"` 가 이 환경의 권한 분류기에 의해 거부되었다. 지시에 따라 vendoring/우회 없이, 패키지가 없으면 skip 하는 테스트로 작성했다. rlo-sdk 는 설치를 시도하지 않았다.

## 한 일
- `ingestion/scrub.py`: 패턴 표 10종(private key, anthropic, openai, google, github, aws, slack, jwt, 대입문, 고엔트로피) → `[REDACTED:<kind>]`.
- `adapters/`: `claude_code.py`(from_cc_jsonl), `ga_l0.py`(read_lenient; llm.response 우선, 없으면 run.end), `exports.py`(Anthropic/OpenAI CSV·JSON 열 매핑 → l0_usage), `common.py`(drop_bodies: 기본 본문 제거, store_bodies 일 때만 scrub 후 유지), `register_all()`.
- `fixtures/ingest/`: anthropic_usage.csv, openai_usage.csv.
- 테스트 `tests/adapters/test_adapters.py`: 12개 (통과 8, skip 4). make check 통과, ingestion 전체 34개 OK.

## 열린 문제
- 설치 불가로 핀된 패키지의 실제 이벤트 형태(필드명 `type`/`data`/`at`, `reported_*_tokens`, usage 필드명)를 확인하지 못했다. 가정에 근거한 매핑이며, 스텁 파서로만 시험했다. 패키지가 있는 환경에서 skip 테스트 4개와 매핑을 먼저 검증해야 한다.
- Claude Code / ga L0 실제 fixture 는 형태를 몰라 만들지 않았다.
- `rlo.usage_formats` 를 사용하는 context 계산은 구현하지 않았다(패키지 API 미확인).
- 스키마 DB 테스트는 실행하지 않았다.

## baseline 요청
- 이 환경에서 pinned git 패키지 설치 허용(또는 사전 설치), 이후 후속 세션에서 검증 및 cc/ga fixture 추가.

## 수정 (baseline 피드백 반영)
- `l0_usage` 는 `(fields, null_names)` 튜플을 돌려준다: exports.py 가 풀어서 쓰고, `common.l0_tokens` 가 l0 이름 → CallIn 열로 옮긴다(null 은 None 유지, 5m/1h 분할이 없으면 총 캐시 쓰기를 5m 열에).
- 열 매핑 표를 "내보내기 열 → usage dict 키" 로 바로잡았다(이전엔 열 이름을 그대로 l0_usage 에 넘김). OpenAI 의 키 이름(`input_tokens`, `input_cached_tokens`, `output_tokens`)은 실제 l0_usage 로 확인하지 못했다 — 실패하면 baseline 재실행에서 알려 달라.
- 스텁 테스트가 튜플 형태를 쓰도록 `L0TokensTests` 추가. 테스트 15개: 11 통과, 4 skip(패키지 필요).
