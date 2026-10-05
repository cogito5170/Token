import { FC, FormEvent } from "react";
import { Schemas } from "../../../lib/api";

export const TITLE = "리포트";

type Report = Schemas["Report"];
type Period = Schemas["Period"];

interface ReportsViewProps {
  reports: Report[];
  onGenerate: (range: { from: string; to: string }) => void;
  onExport: (id: string, format: "csv" | "json") => void;
}

export const ReportsView: FC<ReportsViewProps> = ({
  reports,
  onGenerate,
  onExport,
}) => {
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const from = (form.elements.namedItem("from") as HTMLInputElement).value;
    const to = (form.elements.namedItem("to") as HTMLInputElement).value;
    onGenerate({ from, to });
  };

  const handleExport = (e: React.MouseEvent<HTMLButtonElement>) => {
    const btn = e.currentTarget;
    const id = btn.dataset.reportId!;
    const format = btn.dataset.export as "csv" | "json";
    onExport(id, format);
  };

  return (
    <div>
      <h1>{TITLE}</h1>
      <form onSubmit={handleSubmit}>
        <label>
          From:
          <input type="date" name="from" required />
        </label>
        <label>
          To:
          <input type="date" name="to" required />
        </label>
        <button type="submit">생성</button>
      </form>

      {reports.length === 0 ? (
        <p>리포트가 없다.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>기간</th>
              <th>생성일</th>
              <th>내보내기</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{`${r.period.from} ~ ${r.period.to}`}</td>
                <td>{r.created_at ?? ""}</td>
                <td>
                  <button
                    data-report-id={r.id}
                    data-export="csv"
                    onClick={handleExport}
                  >
                    CSV
                  </button>
                  <button
                    data-report-id={r.id}
                    data-export="json"
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
    </div>
  );
};
