# 움직임 규칙 (라이브 모니터)

소유: design. 신호별 대응은 `design/encoding.json`(`signals`), 모양 · 분위기 · 한계 값도 같은 파일에 있다
(`figures` · `tiles` · `moods` · `stage` · `limits`). 시간 이름과 easing 은 `design/tokens.json` `motion` 과
`encoding.json` `durations_ms`(같은 키는 같은 값, `travel` 800 ms 만 추가). frontend 는 이 값을 읽기만 하고 새로 만들지 않는다.

## 1. 시간

1. **시간은 이벤트 시간이다.** 모든 움직임은 (t 까지의 MonitorEvent, t) 의 순수 함수다. 렌더러는 벽시계를 직접 읽지 않는다.
   라이브는 t = 지금, 재생은 t = 스크러버 값. 같은 이벤트 + 같은 t = 같은 장면(재생 결정성 시험은 픽셀이 아니라 장면 그래프를 비교).
2. ga 0.6 L0 에는 시각이 없으므로(`at: null`) 경과 · 속도는 `observed_at` 으로 잰다(docs/data-model.md 7.2).
3. **ga 0.6 의 턴은 불투명하다.** turn.started 도, 턴 안 이벤트도 없다. 일하는 figure 는 "running (elapsed)" 만 보이고,
   그것은 `file:node.budget.grow` 가 움직이는 안쪽 입자 + 마지막 `l0:node.started` / `l0:run.end` 이후 경과다.

## 2. 무대

1. **화면 하나, 페이지 없음.** 위에서 아래로: 대기 선반(tile) · 무대(figure, 선, 펄스) · 완료 선반. 오른쪽에 실패 선반.
   무대 테두리가 쉼 테두리(rest rim, 은퇴한 figure). 완료 선반 뒤에 수평선(전체 사용량 대 예산). 스크롤 없이 장면이 축소된다.
2. 어두운 테마. 강조색(파랑) 하나 + 따뜻한 색(주황, 긴장일 때만).

## 3. 모양이 뜻을 나르고, 색은 돕기만 한다

1. **figure 모양 = 역할.** pool.json `roles` 순서대로 circle · rounded_square · hexagon · triangle · diamond · pill.
   일곱 번째 역할부터는 모양을 다시 쓰고 안쪽 홈(notch)을 하나씩 더한다(`i // 6` 개). 색으로 역할을 나누지 않는다.
2. **크기 = 지금 작업에 쓴 양**(면적 ~ sqrt(tokens), 지름 24–72 px). **밝기 = 활동**: running · continuing 100 %,
   waiting_peer 60 %, idle · retiring 40 %, retired 30 %.
3. **고리 = 결과**: verified 닫힌 원, failed 톱니 틈, needs_judgement 열린 틈, budget 평평한 끝.
   은퇴 표시: done 꽉 찬 점, failed 끊긴 윤곽 점, idle 표시 없음.
4. **선 = 관계**: 굵기 1–6 px = pi, pi 가 클수록 두 figure 가 가까워진다. 동료 대기는 팽팽한 줄(tether).
5. **tile = 일감**: 대기 = 윤곽, 잡힘 = figure 에 붙은 윤곽, 완료 = 채움, 실패 = 둘로 갈라짐, 버림 = 점선 1 초. 자식 tile 은 부모와 가는 선.
6. 모든 신호는 `not_color_only` 에 모양 · 크기 · 위치 · 선 굵기 · 밀도 중 하나 이상의 단서를 적는다.

## 4. 분위기(Mood)는 리듬이다

`moods.rules` 의 다섯 가지. 우선순위 all_done > stall > tension > collaboration > pace.

| 분위기 | 조건 | 장면 |
|---|---|---|
| `derived:pace` | 분당 이벤트 수 | 기본 템포 = 0.5 + min(분당, 30) / 20 배. 주변 먼지의 양과 빠르기 |
| `derived:collaboration` | 분당 메시지 ≥ 3 | 스프링 20 % 조임, 펄스가 한 박자에 맞춰짐, 선이 밝아짐 |
| `derived:tension` | 예산 ≥ 80 % · 실패 tile ≥ 2 · 대기 사슬 ≥ 3 | 맥박 1.5 배, 수평선 따뜻한 빛 + 연료 호 눈금 |
| `derived:stall` | 120 초 무신호 + 대기 tile 또는 살아 있는 figure | 템포 0.3 배, 밝기 −20 %, 단어 `wait` |
| `derived:all_done` | 대기 없음 · 살아 있는 것 없음 · 완료 ≥ 1 | 한 줄로 정렬, 한 번 쓸고 멈춤, 단어 `done` |

pace 가 기본 템포를 정하고 collaboration · tension 이 곱한다. stall 은 템포와 밝기를 덮어쓰고, all_done 은 나머지를 끝낸다.
턴 안에서는 경과에 따라 숨이 빨라진다(차분 → 긴장).

## 5. 글자

1. 무대의 글자는 `build` · `wait` · `talk` · `test` · `done` 중 한 단어뿐이다. 소문자, 12 px mono, figure 옆, 2 초 이하
   (stall 의 `wait`, all_done 의 `done` 은 참인 동안 유지). figure 하나에 한 번에 한 단어. 이모지 없음.
2. `test` 는 ga 가 검사 이벤트를 내기 전까지 예약이다(reports/CMD-GC0.md). 지금은 어떤 신호도 쓰지 않는다.
3. `glossary_banned_on_stage` 의 말(node, queue, token, agent, LLM, …)은 무대에 나오지 않는다.
4. **숫자는 호버 · 탭에서만**, 작게(12 px mono, tabular), figure · tile · 선에 붙은 툴팁으로. 신호의 `hover` 가 그 내용이다.

## 6. 움직임 줄이기 (Reduced motion)

`prefers-reduced-motion: reduce` 또는 앱 안 스위치: 이동 · 숨 · 궤도 · 입자 · 쓸기 없음. 상태가 바뀌면 모양을 바로 바꾸고
불투명도 페이드(≤ 120 ms)만 쓴다. 강조는 1 초 유지. 모든 표시 신호는 `reduced_motion` 을 갖고,
그 글에는 `reduced_motion.forbidden_terms` 의 움직임 말이 없다(design/tests/encoding 이 검사).

## 7. 한계

≤ 60 fps, 움직이는 입자 ≤ 400, 동시에 날아가는 펄스가 20 을 넘으면 합친다. figure 12 개에서도 읽힌다.
