# ADR-0004 ga-sdk 를 넣고 돌리는 방식

- 상태: 채택
- 결정:
  - ga-sdk · l0-telemetry · rlo 는 **고정 sha 의존성**이다. sha 와 URL 문자열은 ga-sdk `ga/_pins.py` 를 그대로 따른다(pip 는 URL 철자가 다르면 다른 출처로 본다):
    - `ga-sdk @ git+https://github.com/cogito5170/ga-sdk@03e8dae19132788e108602cf8b732cd670cfe6e9` (0.6.0)
    - `rlo-sdk[sensor] @ git+https://github.com/cogito5170/rlo-SDK@0d92a3de3fed6c67eb6643859588179107977cbd` (0.11.1)
    - `l0-telemetry @ git+https://github.com/cogito5170/Telemetry@f6c7ae26d336965d3558092517e97d37d222c4ea` (0.2.0)
  - 이 저장소는 그 코드를 복사 · 수정하지 않는다. 예외는 `fixtures/final_task/` 의 결과 파일(출처 sha 명시)뿐.
  - 사용처: ingestion(파서: `telemetry.collect.from_cc_jsonl`, `telemetry.ledger.read_lenient`, `telemetry.usage.l0_usage`, `rlo.usage_formats`), advisor/simulation(`rlo.ctxbudget.simulate`), estimation(FINAL_TASK 측정, 나중 ga router `learn` 통계 형식), run(나중: `ga.net.pool` 노드 풀).
  - 플랫폼 안 ga 실행(나중): 별도 `runner` 프로세스가 ga 0.6 노드 풀을 라이브러리로 돌리고, 그 L0(`.ga/telemetry/*.jsonl`, `.ga/nodes/*/telemetry.jsonl`)를 같은 수집 파이프라인으로 흘린다. 실행 시작은 Proposal 승인 뒤에만.
  - 개발 방법으로서의 ga: roadmap.md 의 작업 항목을 `scripts/export_work.py` 로 work/1 로 바꿔 `ga work add` 로 넣고, 각 작업은 `ga judge` 로 판정한다.
- 부족한 기능은 baseline 요청으로 올린다(reports/CMD-GC0.md): 공급자 usage 내보내기 파서, 범용 비밀값 제거기 등. 이 저장소에서 우회 구현을 "파서"로 키우지 않는다(열 매핑 어댑터만 허용).
