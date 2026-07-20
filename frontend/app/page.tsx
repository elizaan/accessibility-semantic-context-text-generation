"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, Zap, GitCompare, FileText } from "lucide-react";
import { getDatasetStats } from "@/lib/api";
import { IS_STATIC_BUILD } from "@/lib/config";
import type { DatasetSource, DatasetStats } from "@/lib/types";

const DATASET_META: Record<DatasetSource, {
  name: string;
  description: string;
  features: string[];
  color: string;
  badge: string;
}> = {
  vistext: {
    name: "VisText",
    description: "Chart–caption pairs with scene graphs and L1–L3 captions (MIT Vis Group)",
    features: ["Scene graph", "Vega-Lite spec", "L1–L3 captions", "Rasterized images"],
    color: "bg-blue-50 border-blue-200",
    badge: "bg-blue-100 text-blue-700",
  },
  olli: {
    name: "Olli Gallery",
    description: "Charts with ARIA navigation trees for screen readers (MIT VIS)",
    features: ["ARIA tree", "Vega-Lite spec", "Keyboard navigation"],
    color: "bg-purple-50 border-purple-200",
    badge: "bg-purple-100 text-purple-700",
  },
  our_world_data: {
    name: "Our World in Data",
    description: "Real-world charts with expert-written domain context and downloadable data tables",
    features: ["Domain context", "Data table", "Source citations"],
    color: "bg-green-50 border-green-200",
    badge: "bg-green-100 text-green-700",
  },
  vcc: {
    name: "Visa Chart Components",
    description: "Chartability-compliant charts with full ARIA roles and keyboard navigation",
    features: ["Full ARIA", "Screen reader descriptions", "Keyboard nav"],
    color: "bg-orange-50 border-orange-200",
    badge: "bg-orange-100 text-orange-700",
  },
  hci_alt_texts: {
    name: "HCI Alt Text Dataset",
    description: "Author-written alt texts from HCI papers, sentence-annotated L1–L4 (Chintalapati et al., ASSETS 2022)",
    features: ["Author alt text", "L1–L4 sentence labels", "Paper context"],
    color: "bg-rose-50 border-rose-200",
    badge: "bg-rose-100 text-rose-700",
  },
};

const QUICK_ACTIONS = [
  {
    icon: Database,
    title: "Browse Datasets",
    description: "Explore charts by source and type",
    href: "/datasets",
    color: "text-blue-600",
  },
  {
    icon: Zap,
    title: "Generate Description",
    description: "Select a chart, toggle features, run LLM",
    href: "/datasets",
    color: "text-purple-600",
  },
  {
    icon: GitCompare,
    title: "Compare Outputs",
    description: "Side-by-side model comparison",
    href: "/compare",
    color: "text-green-600",
  },
  {
    icon: FileText,
    title: "View All Outputs",
    description: "Browse saved generation history",
    href: "/outputs",
    color: "text-orange-600",
  },
  {
    icon: FileText,
    title: "Collections",
    description: "Create and review shared chart sets",
    href: "/collections",
    color: "text-slate-700",
  },
];

export default function HomePage() {
  const [stats, setStats] = useState<DatasetStats[]>([]);

  useEffect(() => {
    getDatasetStats().then(setStats).catch(console.error);
  }, []);

  const countFor = (id: DatasetSource) =>
    stats.find((s) => s.source === id)?.total_charts;

  return (
    <div className="space-y-6">
      {/* Quick actions */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {QUICK_ACTIONS.filter((a) => !IS_STATIC_BUILD || a.href !== "/collections").map((action) => (
            <Link
              key={action.href + action.title}
              href={action.href}
              className="border rounded-lg p-4 hover:bg-accent transition-colors group"
            >
              <action.icon className={`h-5 w-5 mb-2 ${action.color}`} />
              <div className="font-medium text-sm">{action.title}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{action.description}</div>
            </Link>
          ))}
        </div>
      </div>

      {/* Dataset cards */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">Datasets</h2>
        <div className="grid gap-3 grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
          {(Object.keys(DATASET_META) as DatasetSource[])
            .filter((id) => !IS_STATIC_BUILD || countFor(id) !== undefined)
            .map((id) => {
            const ds = DATASET_META[id];
            const count = countFor(id);
            return (
              <Link
                key={id}
                href={`/datasets/${id}`}
                className={`border rounded-xl p-4 hover:shadow-md transition-shadow ${ds.color}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-sm">{ds.name}</h3>
                  <span className={`text-xs font-mono px-1.5 py-0.5 rounded-full shrink-0 ml-1 ${ds.badge}`}>
                    {count !== undefined ? count.toLocaleString() : "—"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{ds.description}</p>
                <div className="flex flex-wrap gap-1">
                  {ds.features.map((f) => (
                    <span key={f} className="text-xs bg-white/70 border rounded px-1.5 py-0.5">
                      {f}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
