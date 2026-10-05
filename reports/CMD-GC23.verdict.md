```ga
{"schema":"report/2","from":"baseline","handled":[{"id":"CMD-GC23","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gracious-meitner-vp49xe","sha":"5a44cf974300ca2a2191ec23f7a58c2dd21db6fc"}],"tests":{"passed":15,"failed":0,"skipped":0},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["baseline ran the adapter tests with the real pinned packages (l0-telemetry f6c7ae2, rlo-sdk 0d92a3d): 15/15 OK after two fix rounds (l0_usage tuple; openai nested prompt_tokens_details)"]},{"id":"D2","state":"met","evidence":["NoOwnParserTests"]},{"id":"D3","state":"met","evidence":["anthropic_key scrub pattern removed -> 2 failures (baseline mutation)"]},{"id":"D4","state":"met","evidence":["BodyTests"]}]}
```

# CMD-GC23 판정 기록 (baseline)

작업 세션의 `reports/CMD-GC23.md` 머리는 첫 부분 보고 때 것 그대로 남아 있고 ga 형식 검사에 걸린다(`status: partial`, `state: unverified` 는 허용값이 아님). 작업 세션은 고정 버전 l0-telemetry 를 설치하지 못해 파서 의존 시험을 돌릴 수 없었으므로, 위 머리는 baseline 이 같은 sha 로 직접 돌린 결과다. baseline 이 중간에 작업 세션에 "ga check 0 hard" 라고 보낸 메시지는 그 파일을 확인하지 않고 한 말이라 틀렸다(BD-377 에 기록).
