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

// Human-readable labels and descriptions for each feature checkbox
export const METADATA_FEATURE_CONFIG: Record<
  MetadataKey,
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
  l4_caption: {
    label: "L4 Caption (Domain Significance)",
    description: "Real-world domain significance — ground truth target",
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

export type LLMProvider = "anthropic" | "openai" | "google" | "meta" | "google_groq";

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
    model_id: "gemini-2.5-flash",
    display_name: "Gemini 2.5 Flash",
    supports_vision: true,
    free: true,
    backend: "google_ai_studio",
  },
  {
    provider: "google",
    model_id: "gemini-2.5-flash-lite",
    display_name: "Gemini 2.5 Flash-Lite",
    supports_vision: true,
    free: true,
    backend: "google_ai_studio",
  },
  {
    provider: "google",
    model_id: "gemini-2.5-pro",
    display_name: "Gemini 2.5 Pro",
    supports_vision: true,
    free: true,   // 2 RPM / 50 req/day limit
    backend: "google_ai_studio",
  },
  // ── Free: Groq ────────────────────────────────────────────────────────────
  {
    provider: "meta",
    model_id: "llama-3.2-11b-vision-preview",
    display_name: "Llama 3.2 Vision 11B",
    supports_vision: true,
    free: true,
    backend: "groq",
  },
  {
    provider: "meta",
    model_id: "llama-3.2-90b-vision-preview",
    display_name: "Llama 3.2 Vision 90B",
    supports_vision: true,
    free: true,
    backend: "groq",
  },
  {
    provider: "meta",
    model_id: "llama-3.3-70b-versatile",
    display_name: "Llama 3.3 70B (text-only)",
    supports_vision: false,
    free: true,
    backend: "groq",
  },
  // ── Free: Groq — Gemma (text-only, image always skipped) ─────────────────
  {
    provider: "google",
    model_id: "gemma-2-9b-it",
    display_name: "Gemma 2 9B (Google AI Studio, text-only)",
    supports_vision: false,
    free: true,
    backend: "google_ai_studio",
  },
  {
    provider: "google_groq",
    model_id: "gemma2-9b-it",
    display_name: "Gemma 2 9B (Groq, text-only)",
    supports_vision: false,
    free: true,
    backend: "groq",
  },
  // ── Paid: Anthropic ───────────────────────────────────────────────────────
  {
    provider: "anthropic",
    model_id: "claude-opus-4-8",
    display_name: "Claude Opus 4.8",
    supports_vision: true,
    free: false,
    backend: "anthropic",
  },
  {
    provider: "anthropic",
    model_id: "claude-sonnet-4-6",
    display_name: "Claude Sonnet 4.6",
    supports_vision: true,
    free: false,
    backend: "anthropic",
  },
  // ── Paid: OpenAI ─────────────────────────────────────────────────────────
  {
    provider: "openai",
    model_id: "gpt-4o",
    display_name: "GPT-4o",
    supports_vision: true,
    free: false,
    backend: "openai",
  },
  {
    provider: "openai",
    model_id: "gpt-4o-mini",
    display_name: "GPT-4o Mini",
    supports_vision: true,
    free: false,
    backend: "openai",
  },
];

// ─── Generation request / response ────────────────────────────────────────────

export interface GenerationRequest {
  chart_id: string;
  model_id: string;
  variant?: number;
  enabled_features: MetadataKey[];
  include_image: boolean;
  custom_prompt_suffix?: string;
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
