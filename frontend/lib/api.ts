import axios from "axios";
import type {
  Chart,
  Collection,
  DatasetSource,
  ChartType,
  DatasetStats,
  GenerationRequest,
  GenerationOutput,
} from "./types";
import { IS_STATIC_BUILD, BASE_PATH } from "./config";
import * as staticAdapter from "./static-adapter";

// FastAPI backend runs locally and reads from /data on disk
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 120_000,
});

// ─── Datasets ─────────────────────────────────────────────────────────────────

export async function getDatasetStats(): Promise<DatasetStats[]> {
  if (IS_STATIC_BUILD) return staticAdapter.getDatasetStats();
  const { data } = await api.get("/datasets/stats");
  return data;
}

export async function listCharts(params: {
  source?: DatasetSource;
  chart_type?: ChartType;
  page?: number;
  page_size?: number;
  summary?: boolean;
}): Promise<{ charts: Chart[]; total: number }> {
  if (IS_STATIC_BUILD) return staticAdapter.listCharts(params);
  const { data } = await api.get("/charts", { params: { summary: true, ...params } });
  return data;
}

export async function getChart(chartId: string): Promise<Chart> {
  if (IS_STATIC_BUILD) return staticAdapter.getChart(chartId);
  const { data } = await api.get(`/charts/${chartId}`);
  return data;
}

// ─── Generation ───────────────────────────────────────────────────────────────
// Disabled in the static build — no backend exists to run generation against.
// The UI never calls these when IS_STATIC_BUILD is true (see page-level
// gating), so these guards are defense-in-depth: fail loudly rather than
// silently 404ing against a nonexistent host.

export async function generateDescription(
  request: GenerationRequest
): Promise<GenerationOutput> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.post("/generate", request);
  return data;
}

export async function getOutputsForChart(
  chartId: string
): Promise<GenerationOutput[]> {
  if (IS_STATIC_BUILD) return staticAdapter.getOutputsForChart(chartId);
  const { data } = await api.get("/outputs", { params: { chart_id: chartId } });
  return data.outputs;
}

export async function getAllOutputs(params?: {
  model_id?: string;
  chart_id?: string;
  page?: number;
  page_size?: number;
}): Promise<{ outputs: GenerationOutput[]; total: number }> {
  if (IS_STATIC_BUILD) return staticAdapter.getAllOutputs(params);
  const { data } = await api.get("/outputs", { params });
  return data;
}

export async function deleteOutput(outputId: string): Promise<void> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  await api.delete(`/outputs/${outputId}`);
}

// ─── Collections ──────────────────────────────────────────────────────────────

export async function getCollections(): Promise<Collection[]> {
  if (IS_STATIC_BUILD) return staticAdapter.getCollections();
  const { data } = await api.get("/collections");
  return data;
}

export async function createCollection(payload: {
  name: string;
  description?: string;
  chart_ids: string[];
}): Promise<Collection> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.post("/collections", payload);
  return data;
}

export async function getCollection(id: string): Promise<Collection> {
  if (IS_STATIC_BUILD) return staticAdapter.getCollection(id);
  const { data } = await api.get(`/collections/${id}`);
  return data;
}

export async function getCollectionCharts(id: string): Promise<Chart[]> {
  if (IS_STATIC_BUILD) return staticAdapter.getCollectionCharts(id);
  const { data } = await api.get(`/collections/${id}/charts`);
  return data;
}

export async function addChartsToCollection(id: string, chart_ids: string[]): Promise<Collection> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.post(`/collections/${id}/charts`, chart_ids);
  return data;
}

export async function removeChartsFromCollection(id: string, chart_ids: string[]): Promise<Collection> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.delete(`/collections/${id}/charts`, { data: chart_ids });
  return data;
}

export async function updateCollection(
  id: string,
  payload: { name?: string; description?: string; chart_ids?: string[] }
): Promise<Collection> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.patch(`/collections/${id}`, payload);
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  await api.delete(`/collections/${id}`);
}

export async function reorderCollections(orderedIds: string[]): Promise<Collection[]> {
  if (IS_STATIC_BUILD) throw new Error("Disabled in the static demo build.");
  const { data } = await api.put("/collections/reorder", orderedIds);
  return data;
}

// Images are served from FastAPI's static file mount of /data in live mode,
// or from the curated frontend/public/static-images/ copy in the static build.
export function getChartImageUrl(imagePath: string): string {
  if (IS_STATIC_BUILD) return `${BASE_PATH}/static-images/${imagePath}`;
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base}/static/${imagePath}`;
}
