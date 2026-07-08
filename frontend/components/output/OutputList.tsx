"use client";

import { useState } from "react";
import { Clock, Cpu, ChevronDown, ChevronUp, Copy, Check, Trash2, RefreshCw } from "lucide-react";
import type { Chart, GenerationOutput } from "@/lib/types";
import { ParsedOutputView } from "./ParsedOutputView";

interface Props {
  outputs: GenerationOutput[];
  chart: Chart;
  onDelete: (outputId: string) => Promise<void>;
  onRegenerate: (output: GenerationOutput) => Promise<void>;
}

export function OutputList({ outputs, onDelete, onRegenerate }: Props) {
  if (outputs.length === 0) {
    return (
      <div className="border rounded-xl p-6 text-center text-sm text-muted-foreground">
        No generations yet. Select features and run Generate.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {outputs.map((output) => (
        <OutputCard
          key={output.output_id}
          output={output}
          onDelete={onDelete}
          onRegenerate={onRegenerate}
        />
      ))}
    </div>
  );
}

interface CardProps {
  output: GenerationOutput;
  onDelete: (outputId: string) => Promise<void>;
  onRegenerate: (output: GenerationOutput) => Promise<void>;
}

function OutputCard({ output, onDelete, onRegenerate }: CardProps) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(output.generated_description);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(output.output_id);
    } finally {
      setDeleting(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await onRegenerate(output);
    } finally {
      setRegenerating(false);
    }
  };

  const date = new Date(output.created_at).toLocaleString();
  const variantLabel = output.variant ? `V${output.variant}` : null;

  return (
    <div className="border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="bg-muted/40 px-4 py-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="text-xs font-mono font-semibold shrink-0">{output.model_id}</span>
          {variantLabel && (
            <span className="text-xs bg-purple-100 text-purple-700 rounded px-1.5 py-0.5 shrink-0">
              {variantLabel}
            </span>
          )}
          <div className="flex gap-1 flex-wrap">
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
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleRegenerate}
            disabled={regenerating || deleting}
            title="Regenerate with same parameters (stateless — no memory of this run)"
            className="p-1.5 rounded-lg text-muted-foreground hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting || regenerating}
            title="Delete this output"
            className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-40"
          >
            <Trash2 className={`h-3.5 w-3.5 ${deleting ? "animate-pulse" : ""}`} />
          </button>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1.5 rounded-lg hover:bg-accent transition-colors"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="p-4 space-y-3">
          {/* Generated description */}
          <div className="relative">
            <button
              onClick={copy}
              className="absolute top-0 right-0 text-muted-foreground hover:text-foreground"
              title="Copy raw response to clipboard"
            >
              {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
            </button>
            <div className="pr-6">
              <ParsedOutputView parsed={output.parsed_output} rawText={output.generated_description} />
            </div>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground border-t pt-2">
            <span className="flex items-center gap-1">
              <Cpu className="h-3 w-3" />
              {output.tokens_used.input} in / {output.tokens_used.output} out
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {(output.latency_ms / 1000).toFixed(1)}s
            </span>
            <span className="ml-auto">{date}</span>
          </div>
        </div>
      )}
    </div>
  );
}
