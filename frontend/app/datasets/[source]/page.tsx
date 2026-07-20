import fs from "node:fs";
import path from "node:path";
import SourceClient from "./SourceClient";

// Route segment config + generateStaticParams must live in a Server
// Component — the actual page body (SourceClient) is a client component.
export const dynamicParams = process.env.NEXT_PUBLIC_STATIC_MODE !== "true";

export async function generateStaticParams() {
  if (process.env.NEXT_PUBLIC_STATIC_MODE !== "true") return [];
  const filePath = path.join(process.cwd(), "public", "static-data", "dataset-stats.json");
  if (!fs.existsSync(filePath)) return [];
  const stats: { source: string }[] = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  return stats.map((s) => ({ source: s.source }));
}

export default function SourcePage() {
  return <SourceClient />;
}
