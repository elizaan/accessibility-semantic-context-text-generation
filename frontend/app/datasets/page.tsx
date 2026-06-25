"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BarChart2, ChevronRight } from "lucide-react";
import { getDatasetStats } from "@/lib/api";
import type { DatasetStats, DatasetSource } from "@/lib/types";

const SOURCE_META: Record<DatasetSource, { label: string; color: string }> = {
  vistext:        { label: "VisText",           color: "bg-blue-100 text-blue-800" },
  olli:           { label: "Olli Gallery",      color: "bg-purple-100 text-purple-800" },
  our_world_data: { label: "Our World in Data", color: "bg-green-100 text-green-800" },
  vcc:            { label: "Visa Chart Comps",  color: "bg-orange-100 text-orange-800" },
  hci_alt_texts:  { label: "HCI Alt Texts",     color: "bg-rose-100 text-rose-800" },
};

export default function DatasetsPage() {
  const [stats, setStats] = useState<DatasetStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDatasetStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Datasets</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Select a dataset to browse charts by type, then open a chart to select accessibility features and generate descriptions.
        </p>
      </div>

      {loading && (
        <div className="text-muted-foreground text-sm">Loading dataset stats…</div>
      )}

      <div className="grid gap-4">
        {(stats.length > 0 ? stats : Object.keys(SOURCE_META) as DatasetSource[]).map((item) => {
          const source = typeof item === "string" ? (item as DatasetSource) : item.source;
          const meta = SOURCE_META[source];
          const totalCharts = typeof item === "object" ? item.total_charts : "—";
          const byType = typeof item === "object" ? item.by_chart_type : {};

          return (
            <Link
              key={source}
              href={`/datasets/${source}`}
              className="border rounded-xl p-5 flex items-center justify-between hover:bg-accent transition-colors group"
            >
              <div className="flex items-center gap-4">
                <BarChart2 className="h-5 w-5 text-muted-foreground" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{meta.label}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${meta.color}`}>
                      {totalCharts} charts
                    </span>
                  </div>
                  {typeof item === "object" && Object.keys(byType).length > 0 && (
                    <div className="flex gap-2 mt-1">
                      {Object.entries(byType).map(([type, count]) => (
                        <span key={type} className="text-xs text-muted-foreground">
                          {type}: {count}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:translate-x-1 transition-transform" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
