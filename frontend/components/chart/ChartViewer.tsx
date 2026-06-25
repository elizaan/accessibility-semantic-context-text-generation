"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import type { Chart } from "@/lib/types";
import { getChartImageUrl } from "@/lib/api";

interface Props {
  chart: Chart;
}

export function ChartViewer({ chart }: Props) {
  const [imgError, setImgError] = useState(false);
  const [activeSection, setActiveSection] = useState<"image" | "ground_truth">("image");

  const imageUrl = getChartImageUrl(chart.image_path);

  return (
    <div className="border rounded-xl overflow-hidden">
      <div className="flex border-b">
        {(["image", "ground_truth"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveSection(tab)}
            className={`flex-1 py-2 text-xs font-medium transition-colors capitalize ${
              activeSection === tab
                ? "bg-background border-b-2 border-primary"
                : "bg-muted/40 text-muted-foreground hover:bg-accent"
            }`}
          >
            {tab === "ground_truth" ? "Ground Truth (L4)" : "Chart Image"}
          </button>
        ))}
      </div>

      {activeSection === "image" && (
        <div className="p-4 space-y-3">
          <div className="bg-muted rounded-lg flex items-center justify-center overflow-hidden aspect-video">
            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                alt={chart.title ?? chart.chart_id}
                className="object-contain w-full h-full"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="text-xs text-muted-foreground text-center p-4">
                <div className="font-mono">{chart.image_path}</div>
                <div className="mt-1">Image not found locally</div>
              </div>
            )}
          </div>

          {/* Chart metadata badges */}
          <div className="space-y-1.5">
            {chart.title && (
              <h2 className="font-semibold text-sm">{chart.title}</h2>
            )}
            <div className="flex flex-wrap gap-1.5 text-xs">
              <span className="bg-muted rounded-full px-2 py-0.5 capitalize">
                {chart.source.replace(/_/g, " ")}
              </span>
              <span className="bg-muted rounded-full px-2 py-0.5 capitalize">
                {chart.chart_type.replace(/_/g, " ")}
              </span>
              <span className="bg-muted rounded-full px-2 py-0.5 capitalize">
                {chart.domain.replace(/_/g, " ")}
              </span>
            </div>
            <div className="font-mono text-xs text-muted-foreground">{chart.chart_id}</div>
            {chart.metadata.source_url && (
              <a
                href={chart.metadata.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
                Source
              </a>
            )}
          </div>
        </div>
      )}

      {activeSection === "ground_truth" && (
        <div className="p-4 space-y-3 text-sm">
          <div className="space-y-3">
            <GroundTruthSection
              label="Context"
              value={chart.ground_truth_description.context}
            />
            <GroundTruthSection
              label="Semantic Meaning"
              value={chart.ground_truth_description.semantic_meaning}
            />
            <GroundTruthSection
              label="Real-World Significance (L4)"
              value={chart.ground_truth_description.real_world_significance}
              highlight
            />
          </div>
          {chart.metadata.l4_caption && (
            <div className="border-t pt-3">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                L4 Caption
              </div>
              <p className="text-sm">{chart.metadata.l4_caption}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GroundTruthSection({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? "bg-amber-50 border border-amber-200" : "bg-muted/40"}`}>
      <div className={`text-xs font-semibold uppercase tracking-wide mb-1 ${highlight ? "text-amber-700" : "text-muted-foreground"}`}>
        {label}
      </div>
      <p className="text-sm">{value || <span className="text-muted-foreground italic">Not annotated yet</span>}</p>
    </div>
  );
}
