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

// FastAPI backend runs locally and reads from /data on disk
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 120_000,
});

// ─── Datasets ─────────────────────────────────────────────────────────────────

export async function getDatasetStats(): Promise<DatasetStats[]> {
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
  const { data } = await api.get("/charts", { params: { summary: true, ...params } });
  return data;
}

export async function getChart(chartId: string): Promise<Chart> {
  const { data } = await api.get(`/charts/${chartId}`);
  return data;
}

// ─── Generation ───────────────────────────────────────────────────────────────

export async function generateDescription(
  request: GenerationRequest
): Promise<GenerationOutput> {
  const { data } = await api.post("/generate", request);
  return data;
}

export async function getOutputsForChart(
  chartId: string
): Promise<GenerationOutput[]> {
  const { data } = await api.get("/outputs", { params: { chart_id: chartId } });
  return data.outputs;
}

export async function getAllOutputs(params?: {
  model_id?: string;
  chart_id?: string;
  page?: number;
  page_size?: number;
}): Promise<{ outputs: GenerationOutput[]; total: number }> {
  const { data } = await api.get("/outputs", { params });
  return data;
}

export async function deleteOutput(outputId: string): Promise<void> {
  await api.delete(`/outputs/${outputId}`);
}

// ─── Collections ──────────────────────────────────────────────────────────────

export async function getCollections(): Promise<Collection[]> {
  const { data } = await api.get("/collections");
  return data;
}

export async function createCollection(payload: {
  name: string;
  description?: string;
  chart_ids: string[];
}): Promise<Collection> {
  const { data } = await api.post("/collections", payload);
  return data;
}

export async function getCollection(id: string): Promise<Collection> {
  const { data } = await api.get(`/collections/${id}`);
  return data;
}

export async function getCollectionCharts(id: string): Promise<Chart[]> {
  const { data } = await api.get(`/collections/${id}/charts`);
  return data;
}

export async function addChartsToCollection(id: string, chart_ids: string[]): Promise<Collection> {
  const { data } = await api.post(`/collections/${id}/charts`, chart_ids);
  return data;
}

export async function removeChartsFromCollection(id: string, chart_ids: string[]): Promise<Collection> {
  const { data } = await api.delete(`/collections/${id}/charts`, { data: chart_ids });
  return data;
}

export async function updateCollection(
  id: string,
  payload: { name?: string; description?: string; chart_ids?: string[] }
): Promise<Collection> {
  const { data } = await api.patch(`/collections/${id}`, payload);
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  await api.delete(`/collections/${id}`);
}

export async function reorderCollections(orderedIds: string[]): Promise<Collection[]> {
  const { data } = await api.put("/collections/reorder", orderedIds);
  return data;
}

// Images are served directly from FastAPI's static file mount of /data
export function getChartImageUrl(imagePath: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base}/static/${imagePath}`;
}
