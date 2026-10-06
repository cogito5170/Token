import type { ReactNode } from "react";
import { join } from "node:path";
import "../styles/globals.css";
import "../styles/screens.css";
import { buildNav } from "../lib/nav/registry";
import { scanRoutes } from "../lib/nav/scan";
import { Shell } from "../lib/shell/Shell";

export const metadata = { title: "ga Console" };

export default function RootLayout({ children }: { children: ReactNode }) {
  const nav = buildNav(scanRoutes(join(process.cwd(), "src/app")), { isAdmin: true });
  return (
    <html lang="ko">
      <body><Shell nav={nav}>{children}</Shell></body>
    </html>
  );
}
