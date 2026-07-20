"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { getChart, getOutputsForChart, deleteOutput, generateDescription } from "@/lib/api";
import { IS_STATIC_BUILD } from "@/lib/config";
import type { Chart, GenerationOutput, DatasetSource, SelectableMetadataKey } from "@/lib/types";
import { MetadataFeaturePanel } from "@/components/chart/MetadataFeaturePanel";
import { GeneratePanel } from "@/components/generate/GeneratePanel";
import { OutputList } from "@/components/output/OutputList";
import { ChartViewer } from "@/components/chart/ChartViewer";

export default function ChartDetailClient() {
  const { source, chartType, chartId } = useParams<{
    source: DatasetSource;
    chartType: string;
    chartId: string;
  }>();

  const [chart, setChart] = useState<Chart | null>(null);
  const [outputs, setOutputs] = useState<GenerationOutput[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"generate" | "outputs">(
    IS_STATIC_BUILD ? "outputs" : "generate"
  );
  const [enabledFeatures, setEnabledFeatures] = useState<SelectableMetadataKey[]>([]);

  useEffect(() => {
    Promise.all([getChart(chartId), getOutputsForChart(chartId)])
      .then(([c, o]) => {
        setChart(c);
        setOutputs(o);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [chartId]);

  const handleNewOutput = (output: GenerationOutput) => {
    setOutputs((prev) => [output, ...prev]);
    setActiveTab("outputs");
  };

  const handleDeleteOutput = async (outputId: string) => {
    await deleteOutput(outputId);
    setOutputs((prev) => prev.filter((o) => o.output_id !== outputId));
  };

  // Stateless regenerate — rebuilds a fresh [SystemMessage, HumanMessage] from
  // the stored output's parameters. No memory of the original run is passed.
  const handleRegenerate = async (output: GenerationOutput) => {
    const newOutput = await generateDescription({
      chart_id: output.chart_id,
      model_id: output.model_id,
      variant: output.variant,
      enabled_features: output.enabled_features.filter(
        (f): f is SelectableMetadataKey => f !== "l4_caption"
      ),
      include_image: output.include_image,
    });
    handleNewOutput(newOutput);
  };

  if (loading) {
    return <div className="text-muted-foreground text-sm">Loading chart…</div>;
  }
  if (!chart) {
    return <div className="text-destructive text-sm">Chart not found.</div>;
  }

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
        <Link href="/datasets" className="hover:underline">Datasets</Link>
        <ChevronRight className="h-3 w-3" />
        <Link href={`/datasets/${source}`} className="hover:underline capitalize">
          {source.replace(/_/g, " ")}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <Link href={`/datasets/${source}`} className="hover:underline capitalize">
          {chartType.replace(/_/g, " ")}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground font-medium">{chart.title ?? chartId}</span>
      </div>

      {/* Main 3-column layout — each column fills the remaining viewport height */}
      <div className="grid grid-cols-12 gap-5">
        {/* Left: chart image + ground truth */}
        <div className="col-span-12 lg:col-span-4 h-[calc(100vh-7rem)] overflow-y-auto pr-1 space-y-4">
          <ChartViewer chart={chart} />
        </div>

        {/* Center: accessibility feature checkboxes — single source of truth */}
        <div className="col-span-12 lg:col-span-4 h-[calc(100vh-7rem)] overflow-y-auto">
          <MetadataFeaturePanel
            chart={chart}
            enabledFeatures={enabledFeatures}
            onChange={setEnabledFeatures}
          />
        </div>

        {/* Right: generate + outputs */}
        <div className="col-span-12 lg:col-span-4 h-[calc(100vh-7rem)] overflow-y-auto pr-1 space-y-4">
          <div className="flex border rounded-lg overflow-hidden">
            <button
              onClick={() => setActiveTab("generate")}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                activeTab === "generate"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background hover:bg-accent"
              }`}
            >
              Generate
            </button>
            <button
              onClick={() => setActiveTab("outputs")}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                activeTab === "outputs"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background hover:bg-accent"
              }`}
            >
              Outputs ({outputs.length})
            </button>
          </div>

          {activeTab === "generate" ? (
            IS_STATIC_BUILD ? (
              <div className="border rounded-xl p-5 text-sm space-y-2 bg-muted/20">
                <p className="font-medium">Generation is disabled in this static demo.</p>
                <p className="text-muted-foreground">
                  This deployed site only shows previously generated results. To generate your
                  own descriptions, clone the repo, add your own API keys to{" "}
                  <code className="text-xs bg-muted px-1 py-0.5 rounded">backend/.env</code>, and
                  run the app locally.
                </p>
              </div>
            ) : (
              <GeneratePanel
                chart={chart}
                enabledFeatures={enabledFeatures}
                onOutput={handleNewOutput}
              />
            )
          ) : IS_STATIC_BUILD ? (
            <OutputList outputs={outputs} chart={chart} />
          ) : (
            <OutputList
              outputs={outputs}
              chart={chart}
              onDelete={handleDeleteOutput}
              onRegenerate={handleRegenerate}
            />
          )}
        </div>
      </div>
    </div>
  );
}
