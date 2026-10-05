```ga
{"schema":"report/2","from":"consulting","handled":[{"id":"CMD-GC34","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/gc34","sha":"9b46125000000000000000000000000000000000"}],"tests":{"passed":58,"failed":0,"skipped":3},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["test_csv_and_json_exports_agree"]},{"id":"D2","state":"met","evidence":["test_every_number_has_provenance_and_source"]},{"id":"D3","state":"met","evidence":["test_export_is_audited_with_ids_only","test_failed_export_is_not_audited_and_bad_input_rejected"]}]}
```

## 한 일

`backend/app/domains/report/**` 구현: `service.py`(생성·내보내기), `api.py`(`generate`, `export`), `router.py`(`/v1/workspaces/{ws}/reports`, `/reports/{report}/export`), `pg_store.py`(reports 테이블), `wiring.py`, `tests/test_report.py`.

- 리포트 본문은 usage(`usage.api.summary`) · savings(`advisor.api.list_findings`, p10/p50/p90 + 합계, ESTIMATED) · budgets(`quota.api.burn`: 한도·누적 list/cli·소진 예상일) · next_period_settings(다음 기간 한도, p50 절감 기대치)로 구성. 모든 숫자는 `{value, unit, provenance, source[, coverage_permille]}`. 알 수 없는 값은 null(0 아님). list/cli 두 비용 척도를 나란히 유지.
- JSON 과 CSV 는 같은 `flatten(body)` 행 목록을 렌더링하므로 일치. CSV 열: section,key,value,unit,provenance,source,coverage_permille.
- `report.export`(report_id·format·rows 만) 와 `report.generate` 를 audit 에 기록, `report.report.generated` 이벤트 발행. 실패한 내보내기는 기록하지 않음.
- 권한: 조회·내보내기 member, 생성 developer+.

## 테스트
report 단위 테스트 10건 통과. `make check`, `make test` 통과(스키마 테스트는 DSN 없어 skip).

## 열린 문제 / baseline 요청
- `quota.api` 에 `list_budgets(ws)` 가 없다. 지금은 `getattr(quota, "list_budgets", lambda ws: [])` 폴백이라 budgets 절이 비어 있다. `quota.api.list_budgets` 추가 요청(반환: `[{"id","limit_microusd",...}]`).
- openapi `Period` 는 `from`/`to`; 라우터는 dict 본문으로 받고 서비스가 검증한다. PG 경로는 DSN 없이 실행해 보지 못했다.
- 위 커밋 sha 는 보고서 커밋 전 값이며 push 후 실제 sha 로 알린다.
