# golden 장면 (CMD-DS3)

`fixtures/monitor/recording.jsonl`(CMD-RN1) 을 정해진 `t`(첫 이벤트 이후 ms) 에서 본 장면의 **뜻**(픽셀이 아님)이다.
frontend 의 `scene(events, t)` 는 각 `t*.json` 과 같은 결과를 내야 한다(CMD-FE2).

- 만드는 법: `python3 -m design.golden.reference` (검사만: `--check`). 표준 라이브러리만 쓰고, 같은 녹화에서 바이트까지 같은 파일이 나온다.
- 기준: `design/encoding.json` (모양 · 상태 · 고리 · 선반 · 선 굵기 · 분위기 · 단어), `design/motion.md`.
- 담는 것: figure 의 상태 · 밝기 · 모양 · 고리 · 줄(tether) · 은퇴 표시 · 단어, 모든 tile 의 선반, 선의 pi · 굵기 · 메시지 수,
  분위기(템포는 정수 permille), 무대 단어, 보이는 단어 목록(`words`, 허용된 단어만).
- 단어 규칙: figure 에 붙는 단어는 그 figure 의 마지막 신호 단어이고 2 초(`max_on_stage_ms`) 동안 보인다. `stall` · `all_done` 단어는 참인 동안 유지된다.
  동료 대기가 풀린 `file:node.state.consults`(peers 빈 목록) 는 `wait` 를 보이지 않는다.
- 버린 일감(`l0:work.dropped`) 은 1 초 동안 `dropped_marks` 에 나온다.
- 시험: `python3 -m unittest discover -s design/tests/golden -t .`
