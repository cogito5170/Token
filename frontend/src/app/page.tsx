import { redirect } from "next/navigation";
import { join } from "node:path";
import { buildNav } from "../lib/nav/registry";
import { scanRoutes } from "../lib/nav/scan";

/** Land on the first registered screen; with none yet, show a placeholder. */
export default function Home() {
  const first = buildNav(scanRoutes(join(process.cwd(), "src/app")))[0]?.items[0];
  if (first) redirect(first.href);
  return <p>화면이 아직 등록되지 않았습니다.</p>;
}
