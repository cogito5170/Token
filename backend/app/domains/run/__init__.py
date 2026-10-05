"""Run domain (run). 1b: 라이브 모니터 읽기 모델 (CMD-RN1); 플랫폼 안 실행은 나중.

`gadir` (stdlib 만 쓰는 .ga 리더) · `snapshot` (이벤트 접기) · `sidecar` (127.0.0.1 읽기 전용 서버). 설계는 docs/data-model.md 7.
"""
DOMAIN = "run"
MVP = False
OWNED_TABLES = ('ga_dirs', 'monitor_recordings', 'runs', 'run_nodes', 'run_events', 'run_messages', 'run_verdicts',)
