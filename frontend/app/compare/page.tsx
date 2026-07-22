"use client";

import { useEffect, useState } from "react";
import { getChart, getChartImageUrl, getOutputsForChart, listCharts } from "@/lib/api";
import { modelDisplayLabel, METADATA_FEATURE_CONFIG } from "@/lib/types";
import type { Chart, GenerationOutput, SelectableMetadataKey } from "@/lib/types";
import { GitCompare, ChevronDown, ChevronUp, Download } from "lucide-react";
import { ParsedOutputView, parseOutputData, SECTION_LABELS } from "@/components/output/ParsedOutputView";

// Same grouping METADATA_FEATURE_CONFIG uses elsewhere (e.g. MetadataFeaturePanel
// on the chart detail page) — reused here so "available metadata" reads
// consistently across the app. Requires the FULL (non-summarized) chart:
// listCharts()'s summarized records replace heavy fields (data_table,
// scene_graph, vega_lite_spec) with a bare `true`, so previewing their
// actual content needs a separate getChart() fetch — see fullChart below.
function groupedAvailableMetadata(chart: Chart): [string, { key: SelectableMetadataKey; label: string }[]][] {
  const groups: Record<string, { key: SelectableMetadataKey; label: string }[]> = {};
  for (const [key, config] of Object.entries(METADATA_FEATURE_CONFIG) as [
    SelectableMetadataKey,
    (typeof METADATA_FEATURE_CONFIG)[SelectableMetadataKey],
  ][]) {
    if (chart.metadata[key] === null) continue; // only show what's actually available
    (groups[config.group] ??= []).push({ key, label: config.label });
  }
  return Object.entries(groups);
}

// Renders the same content shown on a model card — metadata completeness
// scores/justifications, every description section (with its [DIRECT] /
// [DERIVED] / [SPECULATIVE] tags left inline, exactly as displayed), and
// the flag summary — as a plain-text/Markdown document for download.
// Reuses parseOutputData so this can never drift from what the card
// actually renders.
function buildOutputMarkdown(chart: Chart | undefined, modelId: string, output: GenerationOutput): string {
  const lines: string[] = [];
  const title = chart?.title ?? chart?.chart_id ?? output.chart_id;

  lines.push(`# ${title}`);
  lines.push("");
  lines.push(`- Chart ID: ${output.chart_id}`);
  if (chart?.source) lines.push(`- Source: ${chart.source}`);
  lines.push(`- Model: ${modelDisplayLabel(modelId)} (${modelId})`);
  lines.push(`- Variant: V${output.variant}`);
  lines.push(`- Enabled features: ${output.enabled_features.length ? output.enabled_features.join(", ") : "none"}`);
  lines.push(`- Image included: ${output.include_image ? "yes" : "no"}`);
  lines.push(`- Tokens: ${output.tokens_used.input} in / ${output.tokens_used.output} out`);
  lines.push(`- Latency: ${(output.latency_ms / 1000).toFixed(1)}s`);
  lines.push(`- Generated at: ${output.created_at}`);
  lines.push("");

  const data = parseOutputData(output.parsed_output);

  if (!data) {
    lines.push("## Raw output");
    lines.push("");
    lines.push("_Could not parse structured JSON from this response — showing raw output._");
    lines.push("");
    lines.push(output.generated_description);
    return lines.join("\n");
  }

  const { dimEntries, overall, description, flags } = data;

  if (dimEntries.length > 0) {
    lines.push(`## Metadata Completeness${overall !== undefined ? ` (Overall ${overall.toFixed(1)}/5)` : ""}`);
    lines.push("");
    for (const [key, v] of dimEntries) {
      lines.push(`- ${key.replace(/_/g, " ")}: ${v.score}/5`);
      if (v.justification?.trim()) lines.push(`  - ${v.justification.trim()}`);
    }
    lines.push("");
  }

  for (const [key, text] of Object.entries(description)) {
    if (!text) continue;
    lines.push(`## ${SECTION_LABELS[key] ?? key.replace(/_/g, " ")}`);
    lines.push("");
    lines.push(text);
    lines.push("");
  }

  if (flags) {
    lines.push("## Flag Summary");
    lines.push("");
    lines.push(`- direct: ${flags.direct_count ?? 0}`);
    lines.push(`- derived: ${flags.derived_count ?? 0}`);
    lines.push(`- speculative: ${flags.speculative_count ?? 0}`);
    if (flags.unverified_count) lines.push(`- unverified: ${flags.unverified_count}`);
  }

  return lines.join("\n");
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const COLLAPSED_LINES = 6;

// Shows the actual metadata value (not just that it exists) — same
// collapse/expand pattern as MetadataFeaturePanel's preview on the chart
// detail page.
function MetadataValuePreview({ value }: { value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const formatted = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const lines = formatted.split("\n");
  const isLong = lines.length > COLLAPSED_LINES;
  const displayed = expanded ? formatted : lines.slice(0, COLLAPSED_LINES).join("\n");

  return (
    <div className="mt-2 rounded-md border border-green-200 bg-green-50/50 overflow-hidden">
      <pre className="text-xs font-mono text-green-900 px-3 py-2 whitespace-pre-wrap break-words overflow-x-auto leading-relaxed max-h-80 overflow-y-auto">
        {displayed}
        {!expanded && isLong && <span className="text-green-500 not-italic"> …</span>}
      </pre>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-center justify-center gap-1 py-1 border-t border-green-200 text-xs text-green-700 hover:bg-green-100 transition-colors"
        >
          {expanded ? (
            <><ChevronUp className="h-3 w-3" /> Show less</>
          ) : (
            <><ChevronDown className="h-3 w-3" /> Show all {lines.length} lines</>
          )}
        </button>
      )}
    </div>
  );
}

export default function ComparePage() {
  const [charts, setCharts] = useState<Chart[]>([]);
  const [selectedChartId, setSelectedChartId] = useState<string>("");
  const [outputs, setOutputs] = useState<GenerationOutput[]>([]);
  const [loadingCharts, setLoadingCharts] = useState(true);
  const [loadingOutputs, setLoadingOutputs] = useState(false);
  const [variantFilter, setVariantFilter] = useState<number | "all">("all");
  const [imgError, setImgError] = useState(false);
  const [fullChart, setFullChart] = useState<Chart | null>(null);
  const [expandedMetaKey, setExpandedMetaKey] = useState<SelectableMetadataKey | null>(null);

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

  // Full (non-summarized) chart, needed to preview actual metadata
  // content — the list-view Chart objects have heavy fields collapsed to
  // `true` (see getChartImageUrl comment above groupedAvailableMetadata).
  useEffect(() => {
    setFullChart(null);
    if (!selectedChartId) return;
    getChart(selectedChartId).then(setFullChart).catch(console.error);
  }, [selectedChartId]);

  // Reset the variant filter whenever the chart changes — a variant that
  // was valid for the old chart may not exist for the new one.
  useEffect(() => { setVariantFilter("all"); }, [selectedChartId]);
  useEffect(() => { setImgError(false); }, [selectedChartId]);
  useEffect(() => { setExpandedMetaKey(null); }, [selectedChartId]);

  const selectedChart = charts.find((c) => c.chart_id === selectedChartId);

  const filteredOutputs =
    variantFilter === "all" ? outputs : outputs.filter((o) => o.variant === variantFilter);

  // Group outputs by model
  const byModel = filteredOutputs.reduce<Record<string, GenerationOutput[]>>((acc, o) => {
    (acc[o.model_id] ??= []).push(o);
    return acc;
  }, {});

  const modelIds = Object.keys(byModel);

  // Stable "#N within its dataset" number per chart, based on position
  // within its own source's block of the (source-grouped) charts list —
  // matches the numbering shown for the same chart on the Datasets page.
  const chartNumber = new Map<string, number>();
  const perSourceCounter: Record<string, number> = {};
  for (const c of charts) {
    perSourceCounter[c.source] = (perSourceCounter[c.source] ?? 0) + 1;
    chartNumber.set(c.chart_id, perSourceCounter[c.source]);
  }

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
              [{c.source}] #{chartNumber.get(c.chart_id)} {c.title ?? c.chart_id}
            </option>
          ))}
        </select>
      </div>

      {/* Chart image — shown once, above the per-model columns, so the
          descriptions can be checked against what the models actually saw. */}
      {selectedChart && (
        <div className="border rounded-xl p-4">
          <div className="bg-muted rounded-lg flex items-center justify-center overflow-hidden max-h-[50vh]">
            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={getChartImageUrl(selectedChart.image_path)}
                alt={selectedChart.title ?? selectedChart.chart_id}
                className="object-contain max-w-full max-h-[50vh]"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="text-xs text-muted-foreground text-center p-4">
                <div className="font-mono">{selectedChart.image_path}</div>
                <div className="mt-1">Image not found locally</div>
              </div>
            )}
          </div>

          {/* Available metadata for this chart — only fields that actually
              have data, grouped the same way MetadataFeaturePanel groups
              them on the chart detail page. Click a field to see its
              actual content, not just that it exists. */}
          <div className="mt-3 pt-3 border-t">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Available Metadata
            </div>
            {!fullChart ? (
              <div className="text-xs text-muted-foreground">Loading…</div>
            ) : groupedAvailableMetadata(fullChart).length === 0 ? (
              <div className="text-xs text-muted-foreground">None — image only.</div>
            ) : (
              <>
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                  {groupedAvailableMetadata(fullChart).map(([group, fields]) => (
                    <div key={group} className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-muted-foreground">{group}:</span>
                      {fields.map(({ key, label }) => (
                        <button
                          key={key}
                          onClick={() => setExpandedMetaKey((k) => (k === key ? null : key))}
                          className={`text-xs rounded px-1.5 py-0.5 transition-colors ${
                            expandedMetaKey === key
                              ? "bg-green-600 text-white"
                              : "bg-green-50 text-green-700 hover:bg-green-100"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
                {expandedMetaKey && (
                  <MetadataValuePreview value={fullChart.metadata[expandedMetaKey]} />
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Variant filter — lines up the same variant across all model columns
          instead of needing to scroll each column independently to find it. */}
      {!loadingOutputs && outputs.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">Variant:</span>
          <button
            onClick={() => setVariantFilter("all")}
            className={`text-xs rounded-full px-3 py-1 border transition-colors ${
              variantFilter === "all" ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"
            }`}
          >
            All
          </button>
          {[1, 2, 3, 4].map((v) => (
            <button
              key={v}
              onClick={() => setVariantFilter(v)}
              className={`text-xs rounded-full px-3 py-1 border transition-colors ${
                variantFilter === v ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"
              }`}
            >
              V{v}
            </button>
          ))}
        </div>
      )}

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
                <div className="font-mono text-sm font-semibold">{modelDisplayLabel(modelId)}</div>
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
                      <button
                        onClick={() => {
                          const modelSlug = modelId.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
                          downloadTextFile(
                            `${output.chart_id}_${modelSlug}_v${output.variant}.md`,
                            buildOutputMarkdown(selectedChart, modelId, output)
                          );
                        }}
                        title="Download this card as Markdown"
                        className="ml-auto flex items-center gap-1 text-xs rounded px-1.5 py-0.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                      >
                        <Download className="h-3 w-3" /> Download
                      </button>
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
