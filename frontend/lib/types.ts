// ─── Dataset sources and chart types ──────────────────────────────────────────

export type DatasetSource =
  | "vistext"
  | "olli"
  | "our_world_data"
  | "vcc"
  | "hci_alt_texts";

export type ChartType =
  | "bar"
  | "line"
  | "scatter"
  | "heatmap"
  | "box_plot"
  | "other";

export type Domain =
  | "public_health"
  | "climate"
  | "finance"
  | "education"
  | "demographics"
  | "employment"
  | "general";

// ─── Metadata feature keys (each maps to a checkbox) ─────────────────────────

export interface ChartMetadata {
  alt_text: string | null;
  aria_label: string | null;
  aria_describedby: string | null;
  olli_tree: string | null;
  scene_graph: object | null;
  data_table: object[] | null;
  vega_lite_spec: object | null;
  l1_caption: string | null;
  l2_caption: string | null;
  l3_caption: string | null;
  l4_caption: string | null;
  domain_context: string | null;
  stakeholder_context: string | null;
  source_url: string | null;
}

export type MetadataKey = keyof ChartMetadata;

// Every metadata key except l4_caption — the ground-truth target this
// benchmark scores against. It's never sent to the model, so it isn't a
// selectable "feature" at all (unlike the rest, checking it would do nothing).
export type SelectableMetadataKey = Exclude<MetadataKey, "l4_caption">;

// Human-readable labels and descriptions for each feature checkbox
export const METADATA_FEATURE_CONFIG: Record<
  SelectableMetadataKey,
  { label: string; description: string; group: string }
> = {
  alt_text: {
    label: "Alt Text",
    description: "Basic image alternative text",
    group: "Accessibility Markup",
  },
  aria_label: {
    label: "ARIA Label",
    description: "ARIA label attribute for screen readers",
    group: "Accessibility Markup",
  },
  aria_describedby: {
    label: "ARIA Describedby",
    description: "Linked description text via aria-describedby",
    group: "Accessibility Markup",
  },
  olli_tree: {
    label: "Olli Screen Reader Tree",
    description: "Hierarchical ARIA navigation tree from Olli",
    group: "Structural Metadata",
  },
  scene_graph: {
    label: "Scene Graph",
    description: "DOM-like hierarchical scene structure (VisText)",
    group: "Structural Metadata",
  },
  data_table: {
    label: "Data Table",
    description: "Underlying dataset as array of objects",
    group: "Structural Metadata",
  },
  vega_lite_spec: {
    label: "Vega-Lite Spec",
    description: "Machine-readable chart specification",
    group: "Structural Metadata",
  },
  l1_caption: {
    label: "L1 Caption (Construction)",
    description: "Chart construction: axis ranges, type, encodings",
    group: "Captions (Lundgard & Satyanarayan Levels)",
  },
  l2_caption: {
    label: "L2 Caption (Statistics)",
    description: "Statistics and data relations",
    group: "Captions (Lundgard & Satyanarayan Levels)",
  },
  l3_caption: {
    label: "L3 Caption (Trends)",
    description: "Perceptual trends and patterns",
    group: "Captions (Lundgard & Satyanarayan Levels)",
  },
  domain_context: {
    label: "Domain Context",
    description: "Paragraph about real-world stakes",
    group: "Semantic Context",
  },
  stakeholder_context: {
    label: "Stakeholder Context",
    description: "Who uses this data and why",
    group: "Semantic Context",
  },
  source_url: {
    label: "Source URL",
    description: "Original source URL",
    group: "Provenance",
  },
};

// ─── Chart record ─────────────────────────────────────────────────────────────

export interface Chart {
  chart_id: string;
  source: DatasetSource;
  chart_type: ChartType;
  domain: Domain;
  image_path: string;
  title: string | null;
  metadata: ChartMetadata;
  ground_truth_description: {
    context: string;
    semantic_meaning: string;
    real_world_significance: string;
  };
}

// ─── LLM models ───────────────────────────────────────────────────────────────

export type LLMProvider = "anthropic" | "openai" | "google" | "meta";

export interface LLMModel {
  provider: LLMProvider;
  model_id: string;
  display_name: string;
  supports_vision: boolean;
  free: boolean;
  backend: "google_ai_studio" | "groq" | "openai" | "anthropic";
}

// Free models first — these are the primary evaluation set for the benchmark.
// Paid models included for optional comparison but not required.
export const LLM_MODELS: LLMModel[] = [
  // ── Free: Google AI Studio ────────────────────────────────────────────────
  {
    provider: "google",
    model_id: "gemini-3.5-flash",
    display_name: "Gemini 3.5 Flash",
    supports_vision: true,
    free: true, // verify current quota in AI Studio — free-tier limits weren't confirmed at time of writing
    backend: "google_ai_studio",
  },
  // ── Free: Groq ────────────────────────────────────────────────────────────
  // Groq deprecates models frequently (console.groq.com/docs/deprecations) —
  // llama-3.2-*-vision-preview was decommissioned; this is its current
  // vision-capable replacement (console.groq.com/docs/vision).
  {
    provider: "meta",
    model_id: "meta-llama/llama-4-scout-17b-16e-instruct",
    display_name: "Llama 4 Scout 17B (Vision)",
    supports_vision: true,
    free: true,
    backend: "groq",
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-5",
    display_name: "Claude Sonnet 5",
    supports_vision: true,
    free: false,
    backend: "anthropic",
  },
  // ── Paid: OpenAI ─────────────────────────────────────────────────────────
  // Single model by design (workshop-paper scope) — gpt-5.4 is the current
  // base-tier GPT-5-family model with vision, the direct successor to
  // gpt-4o's tier. gpt-4o and bare gpt-5 are both deprecated in OpenAI's
  // API as of this writing.
  {
    provider: "openai",
    model_id: "gpt-5.4",
    display_name: "GPT-5.4",
    supports_vision: true,
    free: false,
    backend: "openai",
  },
];

// ─── Generation request / response ────────────────────────────────────────────

export interface GenerationRequest {
  chart_id: string;
  model_id: string;
  enabled_features: SelectableMetadataKey[];
  include_image: boolean;
  // 1/2/3 are informational only — the backend recomputes the actual
  // condition from enabled_features + include_image, since datasets vary
  // in what metadata they have (see prompt_service.classify_variant).
  // 4 is the one value that's honored as sent — it requests the
  // metacognition test, which can't be inferred from a checkbox state.
  variant?: number;
  custom_prompt_suffix?: string;
}

// ─── Prompt variants ──────────────────────────────────────────────────────────
// Display-only: mirrors backend/app/services/prompt_service.py's
// classify_variant/condition_label. 0-3 are *computed* from whatever's
// checked, not chosen directly; only 4 is an explicit user choice.

export interface VariantConfig {
  id: number;
  name: string;
  description: string;
}

export const VARIANTS: VariantConfig[] = [
  {
    id: 0,
    name: "Custom / Partial Selection",
    description: "A valid run, just not one of the three canonical metadata conditions.",
  },
  {
    id: 1,
    name: "Full Metadata + Image",
    description: "Every accessibility field available for this chart, plus the chart image.",
  },
  {
    id: 2,
    name: "Full Metadata, No Image",
    description: "Same metadata as V1, chart image withheld — isolates what the image adds.",
  },
  {
    id: 3,
    name: "Sparse (Image Only)",
    description: "Chart image only — no metadata selected.",
  },
  {
    id: 4,
    name: "Withheld Metadata",
    description: "Chart image only — rich metadata exists elsewhere but is deliberately withheld (metacognition test).",
  },
];

/**
 * Mirrors backend prompt_service.classify_variant — lets the frontend show
 * a live preview of which condition a selection will resolve to, before
 * the request is sent.
 */
export function classifyVariant(
  chart: Chart,
  enabledFeatures: SelectableMetadataKey[],
  includeImage: boolean
): number {
  const availableKeys = (Object.keys(METADATA_FEATURE_CONFIG) as SelectableMetadataKey[]).filter(
    (k) => chart.metadata[k] !== null
  );
  const available = new Set(availableKeys);
  const selected = new Set(enabledFeatures.filter((f) => available.has(f)));
  const allSelected = available.size > 0 && selected.size === available.size;
  const noneSelected = selected.size === 0;

  if (allSelected && includeImage) return 1;
  if (allSelected && !includeImage) return 2;
  if (noneSelected && includeImage) return 3;
  return 0;
}

export interface GenerationOutput {
  output_id: string;
  chart_id: string;
  dataset_source: DatasetSource;
  model_id: string;
  variant: number;
  enabled_features: MetadataKey[];
  include_image: boolean;
  generated_description: string;
  parsed_output: Record<string, unknown> | null;
  tokens_used: { input: number; output: number };
  latency_ms: number;
  created_at: string;
}

// ─── Collections ──────────────────────────────────────────────────────────────

export interface Collection {
  collection_id: string;
  name: string;
  description: string | null;
  chart_ids: string[];
  created_at: string;
  updated_at: string;
}

// ─── Dataset browsing ─────────────────────────────────────────────────────────

export interface DatasetStats {
  source: DatasetSource;
  total_charts: number;
  by_chart_type: Partial<Record<ChartType, number>>;
  by_domain: Partial<Record<Domain, number>>;
}
