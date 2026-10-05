```ga
{"schema":"report/2","from":"infra","handled":[{"id":"CMD-IF2","rev_seen":1,"status":"done"}],"commits":[{"repo":"cogito5170/Token","branch":"claude/if2","sha":"3df5145a1f8bfdd5e1de6f519bc4be436592c511"}],"tests":{"passed":72,"failed":3,"skipped":23},"change_size":"component","items":[{"id":"D1","state":"met","evidence":["desktop: npx playwright test 14 passed (IF1's 8 shell/unit tests + appimage + replay + 2 new IF2 unit tests); screenshot test writes desktop/test-results/ (untracked), tests/electron-window.png removed","frontend vitest tests/shell/desktop.test.ts 6 passed (Shell bare /live under gaDesktop, liveBase sidecarUrl, GC_STATIC_EXPORT flag)","make check 0 problems; make test OK (3 suites, 23 skipped for missing deps)","frontend vitest: 3 failures + 3 playwright specs picked up by vitest are pre-existing on 963ebb1 (api sync, tokens x2), not touched"]},{"id":"D2","state":"met","evidence":["AppImage 'GA Console Monitor-0.0.1.AppImage' built; tests/appimage.spec.ts launches it headless (APPIMAGE_EXTRACT_AND_RUN) against demo/replay.py and the stage paints","tests/test_replay.py: monotone seq/observed_at, 6 nodes, >=8 messages, red judge (queue.failed) then green, integration done, all_done mood, 0 skipped lines","mutations killed locally: Shell bare=false -> desktop.test fails; liveBase ignoring sidecarUrl -> fails; replay path guard removed -> test_replay fails","demo/preview: 4 PNG + demo.webm 4.5 MB, 1280x800, ~40 s"]},{"id":"D3","state":"met","evidence":["this report; preview paths desktop/demo/preview/{01-design-kickoff,02-collaboration,03-red-judge,04-integration-done}.png and desktop/demo/preview/demo.webm","needs: Apple Developer ID cert + notarization credentials (CSC_LINK, CSC_KEY_PASSWORD, APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID) and a Windows code-signing cert (CSC_LINK, CSC_KEY_PASSWORD) from the owner; none added"]}]}
```

# CMD-IF2 보고

## 한 일
- **frontend**: `next.config.mjs` 는 `GC_STATIC_EXPORT=1` 일 때만 정적 export(기본 불변). `Shell` 은 `window.gaDesktop` 이 있으면 `/live`(`/live/` 포함)에서 로그인 리다이렉트 없이 크롬 없이 렌더. `/live` 는 `gaDesktop.sidecarUrl` 을 `?api` 보다 우선. 판단 로직은 새 파일 `frontend/src/lib/shell/desktop.ts` 에 두었다(순수 함수라 테스트 가능; 지시의 "정확히 이 파일들" 에 더해 이 헬퍼 1개 추가).
- **desktop**: build-renderer 가 env 플래그 사용(복사본 설정 덮어쓰기 제거), preload 의 sessionStorage 자리표시자 제거, 스크린샷 테스트는 `test-results/` 에 쓰고 추적되던 png 삭제. **버그 수정**: 패키징된 앱에서 `main.js` 가 벤더링된 `backend/` 를 찾지 못해 사이드카가 죽던 문제(`../backend` 우선), `asar:false`(사이드카 .py 를 직접 실행하기 때문).
- **설치 파일**: `electron-builder 26.15.3`(고정). Linux AppImage 빌드·헤드리스 실행 확인. mac dmg / win nsis 설정은 있고 서명 없음(`identity: null`). README 에 Mac/Windows 빌드 방법과 필요한 자격 증명 목록. 앱 id `dev.gaconsole.monitor`, 이름 `GA Console Monitor`, 아이콘 `build/icon.png` 자리표시자.
- **데모**: `demo/replay.py`(6 노드, 40 s, 임시 디렉터리 밖 쓰기 거부), `demo/record.mjs`(AppImage 로 실행해 webm + 스크린샷 4장), 검토용 사본 `desktop/demo/preview/`.

## 테스트
desktop playwright 14 통과, frontend 신규 6 통과, python 3 스위트 통과(skip 23 = 의존성 없음). frontend vitest 의 실패 3건(api 스키마 동기화, tokens x2)과 playwright spec 3개 수집 오류는 통합 헤드 963ebb1 에서도 동일(이번 변경과 무관).

## 알아둘 것
- 설치 파일에 Python 3 는 포함되지 않는다(실행 PC 에 `python3` 필요, `GA_PYTHON`).
- 컨테이너에서 Electron 다운로드가 `npm ci` 로는 안 됐다: zip 을 curl 로 받아 checksums.json 의 sha256 과 대조 후 `node_modules/electron/dist` 에 풀었다.
- 설치 파일은 root 에서 `--no-sandbox` 필요(컨테이너 한정).
- electron-builder 가 appimage 도구를 GitHub 에서 내려받는다(첫 빌드 시 네트워크 필요).

## baseline 요청
없음.
