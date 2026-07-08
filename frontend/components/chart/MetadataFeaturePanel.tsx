"use client";

import { useState, useCallback } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { Chart, SelectableMetadataKey } from "@/lib/types";
import { METADATA_FEATURE_CONFIG } from "@/lib/types";

interface Props {
  chart: Chart;
  enabledFeatures: SelectableMetadataKey[];
  onChange: (enabled: SelectableMetadataKey[]) => void;
}

function groupedFeatures() {
  const groups: Record<string, SelectableMetadataKey[]> = {};
  for (const [key, config] of Object.entries(METADATA_FEATURE_CONFIG) as [SelectableMetadataKey, typeof METADATA_FEATURE_CONFIG[SelectableMetadataKey]][]) {
    (groups[config.group] ??= []).push(key);
  }
  return groups;
}

const GROUPS = groupedFeatures();

export function MetadataFeaturePanel({ chart, enabledFeatures, onChange }: Props) {
  const enabled = new Set(enabledFeatures);

  const toggle = useCallback(
    (key: SelectableMetadataKey) => {
      const next = new Set(enabledFeatures);
      next.has(key) ? next.delete(key) : next.add(key);
      onChange(Array.from(next));
    },
    [enabledFeatures, onChange]
  );

  const enableAll = () =>
    onChange(
      (Object.keys(METADATA_FEATURE_CONFIG) as SelectableMetadataKey[]).filter(
        (k) => chart.metadata[k] !== null
      )
    );

  const disableAll = () => onChange([]);

  const availableCount = (Object.keys(METADATA_FEATURE_CONFIG) as SelectableMetadataKey[]).filter(
    (k) => chart.metadata[k] !== null
  ).length;

  const enableGroup = useCallback(
    (keys: SelectableMetadataKey[]) => {
      const available = keys.filter((k) => chart.metadata[k] !== null);
      const next = new Set(enabledFeatures);
      available.forEach((k) => next.add(k));
      onChange(Array.from(next));
    },
    [chart, enabledFeatures, onChange]
  );

  const disableGroup = useCallback(
    (keys: SelectableMetadataKey[]) => {
      const next = new Set(enabledFeatures);
      keys.forEach((k) => next.delete(k));
      onChange(Array.from(next));
    },
    [enabledFeatures, onChange]
  );

  return (
    <div className="border rounded-xl overflow-hidden">
      <div className="bg-muted/50 px-4 py-3 border-b flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-sm">Accessibility Features</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {enabled.size} selected · {availableCount} available for this chart
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={enableAll}
            className="text-xs text-blue-600 hover:underline"
          >
            Enable all
          </button>
          <span className="text-muted-foreground text-xs">·</span>
          <button
            onClick={disableAll}
            className="text-xs text-muted-foreground hover:underline"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="p-4 space-y-5">
        {Object.entries(GROUPS).map(([groupName, keys]) => {
          const groupAvailable = keys.filter((k) => chart.metadata[k] !== null);
          const groupEnabledCount = keys.filter((k) => enabled.has(k)).length;

          return (
          <div key={groupName}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {groupName}
                <span className="ml-1.5 font-normal normal-case text-muted-foreground/70">
                  ({groupEnabledCount}/{groupAvailable.length} available)
                </span>
              </h3>
              <div className="flex gap-1.5 shrink-0">
                <button
                  onClick={() => enableGroup(keys)}
                  disabled={groupAvailable.length === 0}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
                >
                  All
                </button>
                <span className="text-muted-foreground text-xs">·</span>
                <button
                  onClick={() => disableGroup(keys)}
                  disabled={groupEnabledCount === 0}
                  className="text-xs text-muted-foreground hover:underline disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
                >
                  None
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {keys.map((key) => {
                const config = METADATA_FEATURE_CONFIG[key];
                const hasData = chart.metadata[key] !== null;
                const isChecked = enabled.has(key);

                return (
                  <label
                    key={key}
                    className={`flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                      !hasData
                        ? "opacity-40 cursor-not-allowed bg-muted/30"
                        : isChecked
                        ? "bg-blue-50 border-blue-200"
                        : "hover:bg-accent"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={!hasData}
                      onChange={() => toggle(key)}
                      className="mt-0.5 accent-blue-600"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium">{config.label}</span>
                        {!hasData && (
                          <span className="text-xs text-muted-foreground">(not available)</span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{config.description}</p>
                      {/* Inline preview snippet */}
                      {hasData && isChecked && (
                        <MetadataPreview metaKey={key} chart={chart} />
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

const COLLAPSED_LINES = 5;

function MetadataPreview({ metaKey, chart }: { metaKey: SelectableMetadataKey; chart: Chart }) {
  const [expanded, setExpanded] = useState(false);
  const value = chart.metadata[metaKey];
  if (!value) return null;

  // Pretty-print JSON or plain string
  const formatted =
    typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);

  const lines = formatted.split("\n");
  const isLong = lines.length > COLLAPSED_LINES;
  const displayed = expanded ? formatted : lines.slice(0, COLLAPSED_LINES).join("\n");

  return (
    <div className="mt-2 rounded-md border border-blue-200 bg-blue-50/50 overflow-hidden">
      <pre className="text-xs font-mono text-blue-900 px-3 py-2 whitespace-pre overflow-x-auto leading-relaxed">
        {displayed}
        {!expanded && isLong && (
          <span className="text-blue-400 not-italic"> …</span>
        )}
      </pre>
      {isLong && (
        <button
          onClick={(e) => {
            e.preventDefault();
            setExpanded((v) => !v);
          }}
          className="w-full flex items-center justify-center gap-1 py-1 border-t border-blue-200 text-xs text-blue-600 hover:bg-blue-100 transition-colors"
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
