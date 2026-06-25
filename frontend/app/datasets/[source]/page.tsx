"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Check, MousePointer, Bookmark, Plus, X } from "lucide-react";
import { listCharts, getCollections, createCollection, addChartsToCollection, getChartImageUrl } from "@/lib/api";
import type { Chart, ChartType, DatasetSource, Collection } from "@/lib/types";

const CHART_TYPES: ChartType[] = [
  "bar", "line", "scatter", "heatmap", "box_plot", "other",
];

export default function SourcePage() {
  const { source } = useParams<{ source: DatasetSource }>();
  const [allCharts, setAllCharts] = useState<Chart[]>([]);
  const [total, setTotal] = useState(0);
  const [activeType, setActiveType] = useState<ChartType | "all">("all");
  const [loading, setLoading] = useState(true);

  // Selection state
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Save-to-collection dialog
  const [showDialog, setShowDialog] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Fetch all charts once per source — filter client-side so tabs never disappear
  useEffect(() => {
    setLoading(true);
    setAllCharts([]);
    listCharts({ source, page_size: 20000 })
      .then((res) => { setAllCharts(res.charts); setTotal(res.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [source]);

  // Reset selection when switching type filter
  useEffect(() => { setSelected(new Set()); }, [activeType]);

  // All charts grouped by type (for tab counts + "all" view)
  const byType = allCharts.reduce<Partial<Record<ChartType, Chart[]>>>((acc, c) => {
    (acc[c.chart_type] ??= []).push(c);
    return acc;
  }, {});

  // Charts shown in the current view
  const charts = activeType === "all" ? allCharts : (byType[activeType] ?? []);

  const toggleSelect = (chartId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(chartId) ? next.delete(chartId) : next.add(chartId);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(charts.map((c) => c.chart_id))); // charts = currently visible
  const clearSelect = () => setSelected(new Set());

  const openDialog = async () => {
    const cols = await getCollections();
    setCollections(cols);
    setNewName("");
    setNewDesc("");
    setShowDialog(true);
  };

  const saveToNew = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      const col = await createCollection({ name: newName.trim(), description: newDesc.trim() || undefined, chart_ids: Array.from(selected) });
      setSavedMsg(`Saved to "${col.name}"`);
      setShowDialog(false);
      setTimeout(() => setSavedMsg(null), 3000);
      setSelectMode(false);
      setSelected(new Set());
    } finally {
      setSaving(false);
    }
  };

  const saveToExisting = async (colId: string, colName: string) => {
    setSaving(true);
    try {
      await addChartsToCollection(colId, Array.from(selected));
      setSavedMsg(`Added to "${colName}"`);
      setShowDialog(false);
      setTimeout(() => setSavedMsg(null), 3000);
      setSelectMode(false);
      setSelected(new Set());
    } finally {
      setSaving(false);
    }
  };

  const exitSelectMode = () => { setSelectMode(false); setSelected(new Set()); };

  return (
    <div className="space-y-5">
      {/* Breadcrumb + title */}
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
          <Link href="/datasets" className="hover:underline">Datasets</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="capitalize font-medium text-foreground">{source.replace(/_/g, " ")}</span>
        </div>
        <div className="flex items-baseline justify-between">
          <h1 className="text-2xl font-bold capitalize">{source.replace(/_/g, " ")}</h1>
          <div className="flex items-center gap-2">
            {!loading && total > 0 && (
              <span className="text-sm text-muted-foreground">{total.toLocaleString()} charts</span>
            )}
            {!loading && (
              <button
                onClick={() => { setSelectMode((v) => !v); setSelected(new Set()); }}
                className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
                  selectMode ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"
                }`}
              >
                <MousePointer className="h-3.5 w-3.5" />
                {selectMode ? "Cancel" : "Select"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Chart type filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveType("all")}
          className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
            activeType === "all" ? "bg-primary text-primary-foreground border-primary" : "bg-background hover:bg-accent"
          }`}
        >
          All
        </button>
        {CHART_TYPES.filter((t) => (byType[t]?.length ?? 0) > 0).map((t) => (
          <button
            key={t}
            onClick={() => setActiveType(t)}
            className={`px-3 py-1.5 rounded-full text-sm border capitalize transition-colors ${
              activeType === t ? "bg-primary text-primary-foreground border-primary" : "bg-background hover:bg-accent"
            }`}
          >
            {t.replace(/_/g, " ")} ({byType[t]!.length})
          </button>
        ))}
      </div>

      {loading && <div className="text-muted-foreground text-sm">Loading all charts…</div>}

      {/* Tree view */}
      {!loading && (
        <div className="space-y-8">
          {(activeType === "all"
            ? (Object.entries(byType) as [ChartType, Chart[]][])
            : ([[activeType, byType[activeType] ?? []]] as [ChartType, Chart[]][])
          ).map(([type, typeCharts]) => (
            <div key={type}>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                {String(type).replace(/_/g, " ")} ({(typeCharts as Chart[]).length.toLocaleString()})
              </h2>
              <div className="grid gap-2 grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
                {(typeCharts as Chart[]).map((chart) => {
                  const isSelected = selected.has(chart.chart_id);
                  if (selectMode) {
                    return (
                      <div
                        key={chart.chart_id}
                        onClick={() => toggleSelect(chart.chart_id)}
                        className={`border rounded-lg overflow-hidden cursor-pointer relative transition-all ${
                          isSelected ? "ring-2 ring-primary shadow-md" : "hover:shadow-sm"
                        }`}
                      >
                        <div className={`absolute top-2 left-2 z-10 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors ${
                          isSelected ? "bg-primary border-primary" : "bg-white/90 border-gray-300"
                        }`}>
                          {isSelected && <Check className="h-3 w-3 text-white" />}
                        </div>
                        <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                          {chart.image_path ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={getChartImageUrl(chart.image_path)} alt={chart.title ?? ""} className="object-contain w-full h-full" loading="lazy" />
                          ) : (
                            <span className="text-xs text-muted-foreground">No image</span>
                          )}
                        </div>
                        <div className="p-2">
                          <div className="text-xs font-medium line-clamp-2 leading-snug">{chart.title ?? chart.chart_id}</div>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            <span className="text-xs bg-muted rounded px-1 py-0.5">{chart.domain}</span>
                          </div>
                        </div>
                      </div>
                    );
                  }
                  return (
                    <Link
                      key={chart.chart_id}
                      href={`/datasets/${source}/${chart.chart_type}/${chart.chart_id}`}
                      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group"
                    >
                      <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                        {chart.image_path ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={getChartImageUrl(chart.image_path)} alt={chart.title ?? ""} className="object-contain w-full h-full" loading="lazy" />
                        ) : (
                          <span className="text-xs text-muted-foreground">No image</span>
                        )}
                      </div>
                      <div className="p-2">
                        <div className="text-xs font-medium line-clamp-2 leading-snug">{chart.title ?? chart.chart_id}</div>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          <span className="text-xs bg-muted rounded px-1 py-0.5">{chart.domain}</span>
                          {(Object.entries(chart.metadata) as [string, unknown][])
                            .filter(([, v]) => v !== null && v !== false)
                            .slice(0, 2)
                            .map(([k]) => (
                              <span key={k} className="text-xs bg-blue-50 text-blue-700 rounded px-1 py-0.5">{k}</span>
                            ))}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          {allCharts.length === 0 && (
            <div className="text-muted-foreground text-sm">No charts found for this filter.</div>
          )}
        </div>
      )}

      {/* Sticky selection bar */}
      {selectMode && (
        <div className="fixed bottom-0 left-56 right-0 z-50 border-t bg-background/95 backdrop-blur px-6 py-3 flex items-center gap-3 shadow-lg">
          <span className="text-sm font-medium">{selected.size} selected</span>
          <button onClick={selectAll} className="text-xs text-primary hover:underline">Select all ({charts.length} visible)</button>
          <button onClick={clearSelect} className="text-xs text-muted-foreground hover:underline">Clear</button>
          <div className="flex-1" />
          <button onClick={exitSelectMode} className="text-sm px-3 py-1.5 rounded-lg border hover:bg-accent transition-colors flex items-center gap-1.5">
            <X className="h-3.5 w-3.5" /> Cancel
          </button>
          <button
            onClick={openDialog}
            disabled={selected.size === 0}
            className="flex items-center gap-1.5 text-sm px-4 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Bookmark className="h-3.5 w-3.5" /> Save to collection
          </button>
        </div>
      )}

      {/* Toast */}
      {savedMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-green-700 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg flex items-center gap-2">
          <Check className="h-4 w-4" /> {savedMsg}
        </div>
      )}

      {/* Save to collection dialog */}
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) setShowDialog(false); }}>
          <div ref={dialogRef} className="bg-background border rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <h2 className="font-semibold">Save {selected.size} chart{selected.size !== 1 ? "s" : ""} to collection</h2>
              <button onClick={() => setShowDialog(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
              {/* Existing collections */}
              {collections.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Add to existing</p>
                  <div className="space-y-1.5">
                    {collections.map((col) => (
                      <button
                        key={col.collection_id}
                        onClick={() => saveToExisting(col.collection_id, col.name)}
                        disabled={saving}
                        className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-left disabled:opacity-50"
                      >
                        <div>
                          <div className="text-sm font-medium">{col.name}</div>
                          <div className="text-xs text-muted-foreground">{col.chart_ids.length} charts</div>
                        </div>
                        <Plus className="h-4 w-4 text-primary shrink-0" />
                      </button>
                    ))}
                  </div>
                  <div className="border-t mt-4 pt-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Or create new</p>
                  </div>
                </div>
              )}

              {/* Create new */}
              <div className="space-y-3">
                {collections.length === 0 && (
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Create new collection</p>
                )}
                <input
                  autoFocus={collections.length === 0}
                  placeholder="Collection name *"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") saveToNew(); }}
                  className="w-full text-sm border rounded-lg px-3 py-2 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <input
                  placeholder="Description (optional)"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full text-sm border rounded-lg px-3 py-2 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  onClick={saveToNew}
                  disabled={!newName.trim() || saving}
                  className="w-full py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {saving ? "Saving…" : "Create & Save"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Extra bottom padding when selection bar is visible */}
      {selectMode && <div className="h-16" />}
    </div>
  );
}
