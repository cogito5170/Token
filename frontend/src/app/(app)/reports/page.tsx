"use client";

import { useEffect, useState } from "react";
import { api, type Schemas } from "../../../lib/api";
import { getWorkspaceId, getAccessToken } from "../../../lib/auth/session";
import {
  listReports,
  generateReport,
  exportReport,
  exportCsv,
  reportFileName,
} from "./load";
import { ReportsView } from "./ReportsView";

export default function Page() {
  const [reports, setReports] = useState<Schemas["Report"][]>([]);
  const [ws, setWs] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        let workspaceId = getWorkspaceId();
        if (!workspaceId) {
          const wsList = await api().get("/v1/workspaces");
          if (!Array.isArray(wsList) || wsList.length === 0) {
            throw new Error("No workspace available");
          }
          workspaceId = wsList[0].id;
        }
        setWs(workspaceId);
        const resp = await listReports(api(), workspaceId);
        setReports(resp);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleGenerate = async (
    period: { from: string; to: string }
  ): Promise<void> => {
    if (!ws) return;
    try {
      const newReport = await generateReport(api(), ws, period);
      setReports((prev) => [newReport, ...prev]);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleExport = async (
    id: string,
    format: "csv" | "json"
  ): Promise<void> => {
    if (!ws) return;
    try {
      const report = reports.find((r) => r.id === id);
      if (!report) {
        throw new Error("Report not found");
      }
      const fileName = reportFileName(report, format);
      let blob: Blob;
      if (format === "json") {
        const data = await exportReport(api(), ws, id);
        const json = JSON.stringify(data, null, 2);
        blob = new Blob([json], { type: "application/json" });
      } else {
        const csvText = await exportCsv(
          fetch,
          process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
          getAccessToken(),
          ws,
          id
        );
        blob = new Blob([csvText], { type: "text/csv" });
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (loading) {
    return <p>불러오는 중…</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  return (
    <ReportsView
      reports={reports}
      onGenerate={handleGenerate}
      onExport={handleExport}
    />
  );
}
