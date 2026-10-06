import { FC, FormEvent, MouseEvent } from "react";
import { Schemas } from "../../../lib/api";

export const TITLE = "리포트";

export const ReportsView: FC<{
  reports: Schemas["Report"][];
  onGenerate: (range: { from: string; to: string }) => void;
  onExport: (id: string, format: "csv" | "json") => void;
}> = ({ reports, onGenerate, onExport }) => {
  const handleGenerate = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fromInput = form.elements.namedItem("from") as HTMLInputElement;
    const toInput = form.elements.namedItem("to") as HTMLInputElement;
    if (fromInput && toInput) {
      onGenerate({ from: fromInput.value, to: toInput.value });
    }
  };

  const handleExport = (e: MouseEvent<HTMLButtonElement>) => {
    const reportId = e.currentTarget.dataset.reportId;
    const format = e.currentTarget.dataset.export as "csv" | "json";
    if (reportId && format) {
      onExport(reportId, format);
    }
  };

  return (
    <main className="gc-screen" data-screen="reports">
      <h1>{TITLE}</h1>

      <form className="gc-form" onSubmit={handleGenerate}>
        <label>
          시작
          <input type="date" name="from" required />
        </label>
        <label>
          끝
          <input type="date" name="to" required />
        </label>
        <button type="submit">생성</button>
      </form>

      {reports.length === 0 ? (
        <p className="gc-empty">리포트가 없다.</p>
      ) : (
        <table className="gc-table num" aria-label="리포트 목록">
          <thead>
            <tr>
              <th>기간</th>
              <th>만든 때</th>
              <th>내보내기</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.period.from} ~ {r.period.to}</td>
                <td>
                  {r.created_at
                    ? r.created_at.slice(0, 16).replace("T", " ")
                    : "—"}
                </td>
                <td>
                  <button
                    type="button"
                    data-report-id={r.id}
                    data-export="csv"
                    aria-label={`CSV 내려받기 ${r.period.from} ~ ${r.period.to}`}
                    onClick={handleExport}
                  >
                    CSV
                  </button>
                  <button
                    type="button"
                    data-report-id={r.id}
                    data-export="json"
                    aria-label={`JSON 내려받기 ${r.period.from} ~ ${r.period.to}`}
                    onClick={handleExport}
                  >
                    JSON
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
};
