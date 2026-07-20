"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Trash2, Pencil, Check, X, FolderInput } from "lucide-react";
import { getCollection, getCollectionCharts, removeChartsFromCollection, addChartsToCollection, getCollections, updateCollection, getChartImageUrl, getOutputsForChart } from "@/lib/api";
import { IS_STATIC_BUILD } from "@/lib/config";
import { modelDisplayLabel } from "@/lib/types";
import type { Collection, Chart } from "@/lib/types";

// Shows which models already have generated output for this chart, or
// nothing at all if none do yet — keeps ungenerated cards uncluttered.
function GenerationBadges({ modelIds }: { modelIds: string[] | undefined }) {
  if (!modelIds || modelIds.length === 0) return null;
  return (
    <div className="flex gap-1 mt-1 flex-wrap" title={modelIds.join(", ")}>
      {modelIds.map((id) => (
        <span key={id} className="text-xs bg-green-50 text-green-700 rounded px-1 py-0.5">
          ✓ {modelDisplayLabel(id)}
        </span>
      ))}
    </div>
  );
}

export default function CollectionClient() {
  const { id } = useParams<{ id: string }>();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  // chart_id -> distinct model_ids that have generated output for it
  const [modelsByChart, setModelsByChart] = useState<Record<string, string[]>>({});

  // Move-to-collection dialog
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [otherCollections, setOtherCollections] = useState<Collection[]>([]);
  const [moving, setMoving] = useState(false);

  useEffect(() => {
    Promise.all([getCollection(id), getCollectionCharts(id)])
      .then(([col, ch]) => {
        setCollection(col);
        setNameInput(col.name);
        setCharts(ch);

        // Fire off per-chart output lookups in parallel — collections are
        // small enough that this is cheaper than teaching the backend a
        // bulk chart_id filter. Failures are non-fatal; a chart just shows
        // no generation badges rather than blocking the whole page.
        Promise.all(
          ch.map((c) =>
            getOutputsForChart(c.chart_id)
              .then((outputs) => [c.chart_id, outputs] as const)
              .catch(() => [c.chart_id, []] as const)
          )
        ).then((entries) => {
          const byChart: Record<string, string[]> = {};
          for (const [chartId, outputs] of entries) {
            byChart[chartId] = Array.from(new Set(outputs.map((o) => o.model_id)));
          }
          setModelsByChart(byChart);
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const toggleSelect = (chartId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(chartId) ? next.delete(chartId) : next.add(chartId);
      return next;
    });
  };

  const handleRemoveSelected = async () => {
    if (!collection || selected.size === 0) return;
    if (!confirm(`Remove ${selected.size} chart(s) from this collection?`)) return;
    const ids = Array.from(selected);
    const updated = await removeChartsFromCollection(id, ids);
    setCollection(updated);
    setCharts((prev) => prev.filter((c) => !selected.has(c.chart_id)));
    setSelected(new Set());
    setSelectMode(false);
  };

  const openMoveDialog = async () => {
    const cols = await getCollections();
    setOtherCollections(cols.filter((c) => c.collection_id !== id));
    setShowMoveDialog(true);
  };

  const handleMoveSelected = async (targetId: string, targetName: string) => {
    if (!collection || selected.size === 0) return;
    setMoving(true);
    try {
      const ids = Array.from(selected);
      await addChartsToCollection(targetId, ids);
      const updated = await removeChartsFromCollection(id, ids);
      setCollection(updated);
      setCharts((prev) => prev.filter((c) => !selected.has(c.chart_id)));
      setSelected(new Set());
      setSelectMode(false);
      setShowMoveDialog(false);
      alert(`Moved ${ids.length} chart(s) to "${targetName}".`);
    } finally {
      setMoving(false);
    }
  };

  const saveName = async () => {
    if (!collection || !nameInput.trim()) return;
    const updated = await updateCollection(id, { name: nameInput.trim() });
    setCollection(updated);
    setEditingName(false);
  };

  if (loading) return <div className="text-sm text-muted-foreground">Loading…</div>;
  if (!collection) return <div className="text-sm text-destructive">Collection not found.</div>;

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/collections" className="hover:underline">Collections</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground font-medium">{collection.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {!IS_STATIC_BUILD && editingName ? (
            <div className="flex items-center gap-2">
              <input
                autoFocus
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") saveName(); if (e.key === "Escape") setEditingName(false); }}
                className="text-2xl font-bold border-b border-primary bg-transparent outline-none w-full"
              />
              <button onClick={saveName} className="text-green-600 hover:text-green-700"><Check className="h-5 w-5" /></button>
              <button onClick={() => setEditingName(false)} className="text-muted-foreground hover:text-foreground"><X className="h-5 w-5" /></button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{collection.name}</h1>
              {!IS_STATIC_BUILD && (
                <button onClick={() => setEditingName(true)} className="text-muted-foreground hover:text-foreground">
                  <Pencil className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
          <p className="text-sm text-muted-foreground mt-1">
            {charts.length} chart{charts.length !== 1 ? "s" : ""} · updated {new Date(collection.updated_at).toLocaleDateString()}
          </p>
        </div>

        {!IS_STATIC_BUILD && (
          <div className="flex items-center gap-2 shrink-0">
            {selectMode && selected.size > 0 && (
              <>
                <button
                  onClick={openMoveDialog}
                  className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border hover:bg-accent transition-colors"
                >
                  <FolderInput className="h-3.5 w-3.5" /> Move {selected.size}
                </button>
                <button
                  onClick={handleRemoveSelected}
                  className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-destructive text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Remove {selected.size}
                </button>
              </>
            )}
            <button
              onClick={() => { setSelectMode((v) => !v); setSelected(new Set()); }}
              className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${selectMode ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"}`}
            >
              {selectMode ? "Done" : "Select"}
            </button>
          </div>
        )}
      </div>

      {charts.length === 0 && (
        <div className="border rounded-xl p-10 text-center text-sm text-muted-foreground">
          This collection is empty.{" "}
          <Link href="/datasets" className="text-primary hover:underline">Browse datasets</Link> to add charts.
        </div>
      )}

      {/* Chart grid — same style as the dataset source page */}
      <div className="grid gap-2 grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
        {charts.map((chart) => {
          const isSelected = selected.has(chart.chart_id);
          const card = (
            <div
              key={chart.chart_id}
              className={`border rounded-lg overflow-hidden transition-shadow group relative ${
                selectMode ? "cursor-pointer" : "hover:shadow-md"
              } ${isSelected ? "ring-2 ring-primary" : ""}`}
              onClick={selectMode ? () => toggleSelect(chart.chart_id) : undefined}
            >
              {selectMode && (
                <div className={`absolute top-2 left-2 z-10 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors ${
                  isSelected ? "bg-primary border-primary" : "bg-white border-gray-300"
                }`}>
                  {isSelected && <Check className="h-3 w-3 text-white" />}
                </div>
              )}
              <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                {chart.image_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={getChartImageUrl(chart.image_path)}
                    alt={chart.title ?? chart.chart_id}
                    className="object-contain w-full h-full"
                    loading="lazy"
                  />
                ) : (
                  <span className="text-xs text-muted-foreground">No image</span>
                )}
              </div>
              <div className="p-2">
                <div className="text-xs font-medium line-clamp-2 leading-snug">{chart.title ?? chart.chart_id}</div>
                <div className="flex gap-1 mt-1 flex-wrap">
                  <span className="text-xs bg-muted rounded px-1 py-0.5">{chart.source.replace(/_/g, " ")}</span>
                  <span className="text-xs bg-blue-50 text-blue-700 rounded px-1 py-0.5">{chart.chart_type}</span>
                </div>
                <GenerationBadges modelIds={modelsByChart[chart.chart_id]} />
              </div>
            </div>
          );

          return selectMode ? card : (
            <Link
              key={chart.chart_id}
              href={`/datasets/${chart.source}/${chart.chart_type}/${chart.chart_id}`}
              className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group"
            >
              <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                {chart.image_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={getChartImageUrl(chart.image_path)}
                    alt={chart.title ?? chart.chart_id}
                    className="object-contain w-full h-full"
                    loading="lazy"
                  />
                ) : (
                  <span className="text-xs text-muted-foreground">No image</span>
                )}
              </div>
              <div className="p-2">
                <div className="text-xs font-medium line-clamp-2 leading-snug">{chart.title ?? chart.chart_id}</div>
                <div className="flex gap-1 mt-1 flex-wrap">
                  <span className="text-xs bg-muted rounded px-1 py-0.5">{chart.source.replace(/_/g, " ")}</span>
                  <span className="text-xs bg-blue-50 text-blue-700 rounded px-1 py-0.5">{chart.chart_type}</span>
                </div>
                <GenerationBadges modelIds={modelsByChart[chart.chart_id]} />
              </div>
            </Link>
          );
        })}
      </div>

      {/* Move to collection dialog */}
      {!IS_STATIC_BUILD && showMoveDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setShowMoveDialog(false); }}
        >
          <div className="bg-background border rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <h2 className="font-semibold">Move {selected.size} chart{selected.size !== 1 ? "s" : ""} to…</h2>
              <button onClick={() => setShowMoveDialog(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-1.5 max-h-[70vh] overflow-y-auto">
              {otherCollections.length === 0 && (
                <p className="text-sm text-muted-foreground">No other collections yet. Create one from the Collections page first.</p>
              )}
              {otherCollections.map((col) => (
                <button
                  key={col.collection_id}
                  onClick={() => handleMoveSelected(col.collection_id, col.name)}
                  disabled={moving}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-left disabled:opacity-50"
                >
                  <div>
                    <div className="text-sm font-medium">{col.name}</div>
                    <div className="text-xs text-muted-foreground">{col.chart_ids.length} charts</div>
                  </div>
                  <FolderInput className="h-4 w-4 text-primary shrink-0" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
