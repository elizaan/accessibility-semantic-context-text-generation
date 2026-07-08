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

  const imageUrl = getChartImageUrl(chart.image_path);

  return (
    <div className="border rounded-xl overflow-hidden">
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
    </div>
  );
}
