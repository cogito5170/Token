import { StatusChip } from "../../../components";
import { formatMetric } from "../../../lib/format";
import type { Schemas } from "../../../lib/api";

export const TITLE = "내 작업 방식에서 어떤 모델 · 구성이 맞힌 작업당 가장 적게 들고, 내 한도는 어떻게 설정돼 있는가?";

export function StatsTable({ stats }: { stats: Schemas["PersonalStat"][] }) {
  if (!stats.length) return <p className="gc-empty">아직 개인 통계가 없다.</p>;
  return (
    <table className="gc-table num" aria-label="개인 통계">
      <thead><tr><th>종류</th><th>모델</th><th>구조</th><th>문맥</th><th>작업</th><th>정답</th><th>토큰/정답</th><th>비용 list/정답</th></tr></thead>
      <tbody>
        {stats.map((s) => (
          <tr key={`${s.task_kind}|${s.model_id}|${s.structure}|${s.context_mode}`}>
            <td>{s.task_kind}</td><td>{s.model_id}</td><td>{s.structure}</td><td>{s.context_mode}</td><td>{s.tasks}</td><td>{s.correct}</td>
            <td>{s.tokens_per_correct ? formatMetric(s.tokens_per_correct) : "—"}</td>
            <td>{s.cost_list_per_correct ? formatMetric(s.cost_list_per_correct) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Recommendations({ items }: { items: Schemas["Recommendation"][] }) {
  return (
    <section aria-label="추천">
      {items.map((r) => (
        <p key={r.id}><StatusChip provenance="ESTIMATED" /> <strong>{r.headline}</strong> <span className="num">절감 {formatMetric(r.saving)} · 근거 {r.evidence_n} 건</span></p>
      ))}
    </section>
  );
}

const intOrNull = (v: FormDataEntryValue | null) => (v === null || v === "" ? null : Math.trunc(Number(v)));

export function ProfileForm({ profile, onSave }: { profile: Schemas["Profile"]; onSave: (p: Schemas["Profile"]) => void }) {
  return (
    <form className="gc-form" onSubmit={(ev) => {
      ev.preventDefault();
      const d = new FormData(ev.currentTarget);
      onSave({
        ...profile,
        monthly_budget_microusd: intOrNull(d.get("monthly_budget_microusd")),
        task_budget_microusd: intOrNull(d.get("task_budget_microusd")),
        quality_floor_permille: intOrNull(d.get("quality_floor_permille")),
        store_bodies: d.get("store_bodies") === "on",
      });
    }}>
      <label>월 예산 (microusd) <input name="monthly_budget_microusd" type="number" step={1} defaultValue={profile.monthly_budget_microusd ?? ""} /></label>
      <label>작업당 예산 (microusd) <input name="task_budget_microusd" type="number" step={1} defaultValue={profile.task_budget_microusd ?? ""} /></label>
      <label>품질 하한 (permille) <input name="quality_floor_permille" type="number" min={0} max={1000} step={1} defaultValue={profile.quality_floor_permille ?? ""} /></label>
      <label><input name="store_bodies" type="checkbox" defaultChecked={profile.store_bodies} /> 본문 저장</label>
      <button type="submit">저장</button>
    </form>
  );
}

export function ProfileView({ profile, stats, recommendations, onSave }: { profile: Schemas["Profile"]; stats: Schemas["PersonalStat"][]; recommendations: Schemas["Recommendation"][]; onSave: (p: Schemas["Profile"]) => void }) {
  return (
    <main className="gc-screen" data-screen="profile">
      <h1>{TITLE}</h1>
      <Recommendations items={recommendations} />
      <StatsTable stats={stats} />
      <ProfileForm profile={profile} onSave={onSave} />
    </main>
  );
}
