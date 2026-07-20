import fs from "node:fs";
import path from "node:path";
import ChartDetailClient from "./ChartDetailClient";

// Route segment config + generateStaticParams must live in a Server
// Component — the actual page body (ChartDetailClient) is a client component.
export const dynamicParams = process.env.NEXT_PUBLIC_STATIC_MODE !== "true";

export async function generateStaticParams() {
  if (process.env.NEXT_PUBLIC_STATIC_MODE !== "true") return [];
  const filePath = path.join(process.cwd(), "public", "static-data", "charts-all.json");
  if (!fs.existsSync(filePath)) return [];
  const { charts } = JSON.parse(fs.readFileSync(filePath, "utf-8")) as {
    charts: { source: string; chart_type: string; chart_id: string }[];
  };
  return charts.map((c) => ({
    source: c.source,
    chartType: c.chart_type,
    chartId: c.chart_id,
  }));
}

export default function ChartDetailPage() {
  return <ChartDetailClient />;
}
