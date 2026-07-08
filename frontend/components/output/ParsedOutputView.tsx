"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  parsed: Record<string, unknown> | null;
  rawText: string;
}

// Dropped from the scoring rubric — these were near-binary in practice
// (0 if the field wasn't selected, 5 if it was) rather than a meaningful
// graded 0-5 judgment, and dragged "overall" down without signal. Excluded
// here too so older stored outputs display consistently with new ones.
const EXCLUDED_DIMENSIONS = new Set(["domain_expert_context", "stakeholder_impact"]);

const FLAG_STYLES: Record<string, string> = {
  DIRECT: "bg-green-100 text-green-700",
  DERIVED: "bg-blue-100 text-blue-700",
  SPECULATIVE: "bg-amber-100 text-amber-700",
  // Legacy markers from before the DIRECT/DERIVED/SPECULATIVE taxonomy —
  // kept so older stored outputs still render sensibly.
  CONFIRMED: "bg-green-100 text-green-700",
  ESTIMATED: "bg-amber-100 text-amber-700",
  INFERRED: "bg-amber-100 text-amber-700",
  UNVERIFIED: "bg-red-100 text-red-700",
};

// Captures the flag kind and, for DERIVED/SPECULATIVE, the cited basis
// after the colon, e.g. "[SPECULATIVE: general knowledge of NFL economics]".
const FLAG_PATTERN =
  /\[(DIRECT|DERIVED|SPECULATIVE|CONFIRMED|ESTIMATED|INFERRED|UNVERIFIED)(?::\s*([^\]]*))?\]/g;

const SCORE_COLOR = (score: number, max: number) => {
  const ratio = score / max;
  if (ratio >= 0.75) return "bg-green-500";
  if (ratio >= 0.4) return "bg-amber-500";
  return "bg-red-400";
};

function FlaggedText({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  FLAG_PATTERN.lastIndex = 0;
  let key = 0;

  while ((match = FLAG_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const kind = match[1];
    const detail = match[2]?.trim();
    parts.push(
      <span
        key={key++}
        className="inline-flex items-baseline gap-1 mx-0.5 align-middle"
        title={detail || undefined}
      >
        <span
          className={`inline-block text-[10px] font-semibold uppercase tracking-wide rounded px-1 py-0.5 ${
            FLAG_STYLES[kind] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {kind}
        </span>
        {detail && <span className="text-[10px] text-muted-foreground italic">({detail})</span>}
      </span>
    );
    lastIndex = FLAG_PATTERN.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <p className="text-sm leading-relaxed">{parts}</p>;
}

function ScoreRow({
  label,
  score,
  justification,
  max = 5,
}: {
  label: string;
  score: number;
  justification?: string;
  max?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasJustification = !!justification?.trim();

  return (
    <div>
      <button
        type="button"
        onClick={() => hasJustification && setExpanded((v) => !v)}
        disabled={!hasJustification}
        className="w-full flex items-center gap-2 text-left disabled:cursor-default"
      >
        <span className="text-xs text-muted-foreground w-36 shrink-0 capitalize">
          {label.replace(/_/g, " ")}
        </span>
        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full ${SCORE_COLOR(score, max)}`}
            style={{ width: `${(score / max) * 100}%` }}
          />
        </div>
        <span className="text-xs font-mono w-8 text-right shrink-0">
          {score}/{max}
        </span>
        {hasJustification &&
          (expanded ? (
            <ChevronUp className="h-3 w-3 text-muted-foreground shrink-0" />
          ) : (
            <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
          ))}
      </button>
      {expanded && hasJustification && (
        <p className="text-xs text-muted-foreground mt-1 pl-[9.5rem] pr-4 leading-relaxed">
          {justification}
        </p>
      )}
    </div>
  );
}

const SECTION_LABELS: Record<string, string> = {
  contextual_insights: "Contextual Insights",
  domain_specific_explanations: "Domain-Specific Explanations",
  real_world_significance: "Real-World Significance",
  other: "Other",
};

export function ParsedOutputView({ parsed, rawText }: Props) {
  if (!parsed) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1">
          Could not parse structured JSON from this response — showing raw output.
        </p>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{rawText}</p>
      </div>
    );
  }

  const identification = parsed.identification as
    | { metadata_completeness?: Record<string, unknown> }
    | undefined;
  const dims = identification?.metadata_completeness ?? {};

  const dimEntries = Object.entries(dims)
    .filter(([key]) => key !== "overall" && !EXCLUDED_DIMENSIONS.has(key))
    .map(([key, val]) => [key, val as { score?: number; justification?: string }] as const)
    .filter((entry): entry is [string, { score: number; justification?: string }] =>
      typeof entry[1].score === "number"
    );

  // Recomputed rather than trusting the stored "overall" — older outputs
  // averaged in the two excluded dimensions, which understates the real
  // completeness of what's left once those are dropped.
  const overall =
    dimEntries.length > 0
      ? dimEntries.reduce((sum, [, v]) => sum + v.score, 0) / dimEntries.length
      : undefined;

  const description = (parsed.generated_description ?? {}) as Record<string, string>;

  const flags = parsed.flags as
    | {
        direct_count?: number;
        derived_count?: number;
        speculative_count?: number;
        unverified_count?: number; // legacy — pre-DIRECT/DERIVED/SPECULATIVE outputs
        total_flag_count?: number;
      }
    | undefined;

  return (
    <div className="space-y-4">
      {/* Identification scores */}
      {dimEntries.length > 0 && (
        <div className="rounded-lg border bg-muted/20 p-3 space-y-1.5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Metadata Completeness
            </span>
            {overall !== undefined && (
              <span className="text-xs font-mono font-semibold">
                Overall {overall.toFixed(1)}/5
              </span>
            )}
          </div>
          {dimEntries.map(([key, v]) => (
            <ScoreRow key={key} label={key} score={v.score} justification={v.justification} />
          ))}
        </div>
      )}

      {/* Generated description sections */}
      <div className="space-y-3">
        {Object.entries(description).map(([key, text]) =>
          text ? (
            <div key={key}>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                {SECTION_LABELS[key] ?? key.replace(/_/g, " ")}
              </h4>
              <FlaggedText text={text} />
            </div>
          ) : null
        )}
      </div>

      {/* Flag summary */}
      {flags && (
        <div className="flex items-center gap-2 text-xs border-t pt-2">
          <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700">
            direct {flags.direct_count ?? 0}
          </span>
          <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
            derived {flags.derived_count ?? 0}
          </span>
          <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
            speculative {flags.speculative_count ?? 0}
          </span>
          {/* Legacy outputs generated before the DIRECT/DERIVED/SPECULATIVE
              taxonomy may still carry an unverified count. */}
          {!!flags.unverified_count && (
            <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700">
              unverified {flags.unverified_count}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
