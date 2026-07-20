// Read-only data layer backing frontend/lib/api.ts when IS_STATIC_BUILD is
// true. Fetches the curated JSON produced by scripts/export_static_site_data.py
// (frontend/public/static-data/) instead of hitting the FastAPI backend.
import { BASE_PATH } from "./config";
import type {
  Chart,
  Collection,
  DatasetSource,
  ChartType,
  DatasetStats,
  GenerationOutput,
} from "./types";

const cache = new Map<string, Promise<unknown>>();

async function fetchJson<T>(relPath: string): Promise<T> {
  const url = `${BASE_PATH}/static-data/${relPath}`;
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url).then((res) => {
        if (!res.ok) throw new Error(`Static data fetch failed: ${url} (${res.status})`);
        return res.json();
      })
    );
  }
  return cache.get(url) as Promise<T>;
}

function paginate<T>(items: T[], page = 1, pageSize = 50): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export async function getDatasetStats(): Promise<DatasetStats[]> {
  return fetchJson<DatasetStats[]>("dataset-stats.json");
}

export async function listCharts(params: {
  source?: DatasetSource;
  chart_type?: ChartType;
  page?: number;
  page_size?: number;
}): Promise<{ charts: Chart[]; total: number }> {
  const { charts } = params.source
    ? await fetchJson<{ charts: Chart[]; total: number }>(`charts-by-source/${params.source}.json`)
    : await fetchJson<{ charts: Chart[]; total: number }>("charts-all.json");

  const filtered = params.chart_type ? charts.filter((c) => c.chart_type === params.chart_type) : charts;
  return { charts: paginate(filtered, params.page, params.page_size), total: filtered.length };
}

export async function getChart(chartId: string): Promise<Chart> {
  return fetchJson<Chart>(`charts/${chartId}.json`);
}

export async function getOutputsForChart(chartId: string): Promise<GenerationOutput[]> {
  return fetchJson<GenerationOutput[]>(`outputs-by-chart/${chartId}.json`);
}

export async function getAllOutputs(params?: {
  model_id?: string;
  chart_id?: string;
  page?: number;
  page_size?: number;
}): Promise<{ outputs: GenerationOutput[]; total: number }> {
  const { outputs } = await fetchJson<{ outputs: GenerationOutput[]; total: number }>("outputs-all.json");
  const filtered = outputs.filter(
    (o) =>
      (!params?.model_id || o.model_id === params.model_id) &&
      (!params?.chart_id || o.chart_id === params.chart_id)
  );
  return { outputs: paginate(filtered, params?.page, params?.page_size), total: filtered.length };
}

export async function getCollections(): Promise<Collection[]> {
  return fetchJson<Collection[]>("collections.json");
}

export async function getCollection(id: string): Promise<Collection> {
  return fetchJson<Collection>(`collections/${id}.json`);
}

export async function getCollectionCharts(id: string): Promise<Chart[]> {
  return fetchJson<Chart[]>(`collection-charts/${id}.json`);
}
