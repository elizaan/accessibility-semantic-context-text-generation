"use client";

import { useState } from "react";
import { Zap, ChevronDown, ChevronUp, Eye, EyeOff } from "lucide-react";
import { generateDescription } from "@/lib/api";
import type { Chart, GenerationOutput, LLMModel, SelectableMetadataKey } from "@/lib/types";
import { LLM_MODELS, VARIANTS, classifyVariant } from "@/lib/types";

interface Props {
  chart: Chart;
  enabledFeatures: SelectableMetadataKey[];
  onOutput: (output: GenerationOutput) => void;
}

export function GeneratePanel({ chart, enabledFeatures, onOutput }: Props) {
  const [selectedModel, setSelectedModel] = useState<LLMModel>(LLM_MODELS[0]);
  const [includeImage, setIncludeImage] = useState(true);
  const [metacognitionMode, setMetacognitionMode] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPromptEditor, setShowPromptEditor] = useState(false);

  const imageWillAttach = includeImage && selectedModel.supports_vision;

  // Live preview of which canonical condition this selection resolves to —
  // mirrors backend prompt_service.classify_variant exactly, so what's shown
  // here before generating matches what actually gets tagged on the output.
  const computedVariant = metacognitionMode ? 4 : classifyVariant(chart, enabledFeatures, imageWillAttach);
  const variantInfo = VARIANTS.find((v) => v.id === computedVariant)!;

  const canGenerate = metacognitionMode ? imageWillAttach : enabledFeatures.length > 0 || imageWillAttach;

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setLoading(true);
    setError(null);
    try {
      const output = await generateDescription({
        chart_id: chart.chart_id,
        model_id: selectedModel.model_id,
        enabled_features: enabledFeatures,
        include_image: includeImage,
        variant: metacognitionMode ? 4 : undefined,
        custom_prompt_suffix: customPrompt || undefined,
      });
      onOutput(output);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  // Group models by provider
  const byProvider = LLM_MODELS.reduce<Record<string, LLMModel[]>>((acc, m) => {
    (acc[m.provider] ??= []).push(m);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {/* Condition — computed live from feature checkboxes + image toggle */}
      <div className="border rounded-xl overflow-hidden">
        <div className="bg-muted/50 px-4 py-3 border-b flex items-center justify-between">
          <h2 className="font-semibold text-sm">Condition</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-purple-100 text-purple-700">
            V{variantInfo.id}: {variantInfo.name}
          </span>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-xs text-muted-foreground">{variantInfo.description}</p>

          {!metacognitionMode && (
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">Include Chart Image</div>
                <div className="text-xs text-muted-foreground">
                  {selectedModel.supports_vision
                    ? "Vision-capable model selected"
                    : "Model does not support vision"}
                </div>
              </div>
              <button
                onClick={() => setIncludeImage((v) => !v)}
                disabled={!selectedModel.supports_vision}
                className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
                  imageWillAttach
                    ? "bg-blue-50 border-blue-200 text-blue-700"
                    : "text-muted-foreground"
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {imageWillAttach ? (
                  <>
                    <Eye className="h-3.5 w-3.5" /> On
                  </>
                ) : (
                  <>
                    <EyeOff className="h-3.5 w-3.5" /> Off
                  </>
                )}
              </button>
            </div>
          )}

          <label className="flex items-start gap-2.5 pt-2 border-t cursor-pointer">
            <input
              type="checkbox"
              checked={metacognitionMode}
              onChange={(e) => setMetacognitionMode(e.target.checked)}
              className="mt-0.5 accent-blue-600"
            />
            <div>
              <div className="text-sm font-medium">Metacognition Test (V4)</div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Chart image only — the model is told rich metadata exists for this chart but
                was deliberately withheld. Feature checkboxes are ignored in this mode.
              </p>
            </div>
          </label>
        </div>
        {metacognitionMode && !selectedModel.supports_vision && (
          <p className="text-xs text-amber-600 bg-amber-50 px-4 py-2 border-t">
            {selectedModel.display_name} does not support vision — the metacognition test
            needs an image, so switch to a vision-capable model.
          </p>
        )}
        {computedVariant === 0 && !metacognitionMode && (
          <p className="text-xs text-muted-foreground px-4 py-2 border-t">
            This is a valid run, just not one of the three canonical conditions — check every
            available feature (or none) to hit V1/V2/V3.
          </p>
        )}
      </div>

      {/* Model selector */}
      <div className="border rounded-xl overflow-hidden">
        <div className="bg-muted/50 px-4 py-3 border-b">
          <h2 className="font-semibold text-sm">LLM Model</h2>
        </div>
        <div className="p-4 space-y-3">
          {Object.entries(byProvider).map(([provider, models]) => (
            <div key={provider}>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 capitalize">
                {provider}
              </div>
              <div className="space-y-1">
                {models.map((m) => (
                  <label
                    key={m.model_id}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                      selectedModel.model_id === m.model_id
                        ? "bg-primary/5 border-primary/30"
                        : "hover:bg-accent"
                    }`}
                  >
                    <input
                      type="radio"
                      name="model"
                      value={m.model_id}
                      checked={selectedModel.model_id === m.model_id}
                      onChange={() => setSelectedModel(m)}
                      className="accent-blue-600"
                    />
                    <div className="flex-1">
                      <span className="text-sm font-medium">{m.display_name}</span>
                    </div>
                    {m.supports_vision && (
                      <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                        Vision
                      </span>
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Custom prompt suffix (collapsible) */}
      <div className="border rounded-xl overflow-hidden">
        <button
          onClick={() => setShowPromptEditor((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-accent transition-colors"
        >
          <span>Custom Prompt Suffix</span>
          {showPromptEditor ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {showPromptEditor && (
          <div className="px-4 pb-4 border-t pt-3">
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              rows={4}
              placeholder="Append additional instructions to the generated prompt…"
              className="w-full text-sm border rounded-lg p-2.5 resize-none font-mono bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        )}
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={!canGenerate || loading}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-primary-foreground font-semibold text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Zap className="h-4 w-4" />
        {loading ? "Generating…" : "Generate Description"}
      </button>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {!canGenerate && (
        <p className="text-xs text-muted-foreground text-center">
          {metacognitionMode
            ? "The metacognition test needs a vision-capable model — none is selected."
            : "Enable at least one accessibility feature, or include the chart image with a vision-capable model."}
        </p>
      )}
    </div>
  );
}
