"use client";

import { useEffect, useState } from "react";
import { getOutputsForChart, listCharts } from "@/lib/api";
import type { Chart, GenerationOutput } from "@/lib/types";
import { GitCompare } from "lucide-react";
import { ParsedOutputView } from "@/components/output/ParsedOutputView";

export default function ComparePage() {
  const [charts, setCharts] = useState<Chart[]>([]);
  const [selectedChartId, setSelectedChartId] = useState<string>("");
  const [outputs, setOutputs] = useState<GenerationOutput[]>([]);
  const [loadingCharts, setLoadingCharts] = useState(true);
  const [loadingOutputs, setLoadingOutputs] = useState(false);

  useEffect(() => {
    listCharts({ page_size: 200 })
      .then((res) => setCharts(res.charts))
      .catch(console.error)
      .finally(() => setLoadingCharts(false));
  }, []);

  useEffect(() => {
    if (!selectedChartId) return;
    setLoadingOutputs(true);
    getOutputsForChart(selectedChartId)
      .then(setOutputs)
      .catch(console.error)
      .finally(() => setLoadingOutputs(false));
  }, [selectedChartId]);

  // Group outputs by model
  const byModel = outputs.reduce<Record<string, GenerationOutput[]>>((acc, o) => {
    (acc[o.model_id] ??= []).push(o);
    return acc;
  }, {});

  const modelIds = Object.keys(byModel);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <GitCompare className="h-6 w-6" /> Compare Outputs
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Pick a chart to see all generated descriptions side-by-side, grouped by model and feature variant.
        </p>
      </div>

      {/* Chart selector */}
      <div className="border rounded-xl p-4">
        <label className="text-sm font-medium block mb-2">Select Chart</label>
        <select
          value={selectedChartId}
          onChange={(e) => setSelectedChartId(e.target.value)}
          className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          disabled={loadingCharts}
        >
          <option value="">— choose a chart —</option>
          {charts.map((c) => (
            <option key={c.chart_id} value={c.chart_id}>
              [{c.source}] {c.title ?? c.chart_id}
            </option>
          ))}
        </select>
      </div>

      {loadingOutputs && (
        <div className="text-muted-foreground text-sm">Loading outputs…</div>
      )}

      {/* Side-by-side columns, one per model */}
      {!loadingOutputs && selectedChartId && modelIds.length === 0 && (
        <div className="text-muted-foreground text-sm">
          No outputs saved for this chart yet. Open the chart and generate some descriptions first.
        </div>
      )}

      {modelIds.length > 0 && (
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(modelIds.length, 3)}, 1fr)` }}>
          {modelIds.map((modelId) => (
            <div key={modelId} className="border rounded-xl overflow-hidden">
              <div className="bg-muted/50 px-4 py-2.5 border-b">
                <div className="font-mono text-sm font-semibold">{modelId}</div>
                <div className="text-xs text-muted-foreground">{byModel[modelId].length} runs</div>
              </div>
              <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
                {byModel[modelId].map((output) => (
                  <div key={output.output_id} className="space-y-2">
                    {/* Feature variant badge row */}
                    <div className="flex flex-wrap gap-1 items-center">
                      <span className="text-xs bg-purple-100 text-purple-700 rounded px-1.5 py-0.5">
                        V{output.variant}
                      </span>
                      {output.enabled_features.map((f) => (
                        <span key={f} className="text-xs bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">
                          {f}
                        </span>
                      ))}
                      <span
                        className={`text-xs rounded px-1.5 py-0.5 ${
                          output.include_image
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {output.include_image ? "+image" : "no image"}
                      </span>
                    </div>
                    <ParsedOutputView parsed={output.parsed_output} rawText={output.generated_description} />
                    <div className="text-xs text-muted-foreground border-t pt-1">
                      {output.tokens_used.input}+{output.tokens_used.output} tok ·{" "}
                      {(output.latency_ms / 1000).toFixed(1)}s
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
