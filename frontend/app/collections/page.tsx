"use client";

import { useEffect, useState, type DragEvent } from "react";
import Link from "next/link";
import { Bookmark, ChevronRight, Plus, Trash2, Pencil, Check, X, GripVertical } from "lucide-react";
import { createCollection, deleteCollection, getCollections, updateCollection, reorderCollections } from "@/lib/api";
import type { Collection } from "@/lib/types";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  useEffect(() => {
    getCollections()
      .then(setCollections)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const refreshCollections = async () => {
    const data = await getCollections();
    setCollections(data);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await createCollection({
        name: name.trim(),
        description: description.trim() || undefined,
        chart_ids: [],
      });
      setName("");
      setDescription("");
      await refreshCollections();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string, collectionName: string) => {
    if (!confirm(`Delete collection "${collectionName}"?`)) return;
    await deleteCollection(id);
    setCollections((prev) => prev.filter((c) => c.collection_id !== id));
  };

  const startEdit = (col: Collection) => {
    setEditingId(col.collection_id);
    setEditName(col.name);
  };

  const cancelEdit = () => setEditingId(null);

  const saveEdit = async (id: string) => {
    if (!editName.trim()) return;
    const updated = await updateCollection(id, { name: editName.trim() });
    setCollections((prev) => prev.map((c) => (c.collection_id === id ? updated : c)));
    setEditingId(null);
  };

  const handleDragOver = (e: DragEvent, id: string) => {
    e.preventDefault();
    if (id !== draggedId) setDragOverId(id);
  };

  const handleDrop = async (e: DragEvent, targetId: string) => {
    e.preventDefault();
    const sourceId = draggedId;
    setDraggedId(null);
    setDragOverId(null);
    if (!sourceId || sourceId === targetId) return;

    const prevOrder = collections;
    const newOrder = [...collections];
    const fromIdx = newOrder.findIndex((c) => c.collection_id === sourceId);
    const toIdx = newOrder.findIndex((c) => c.collection_id === targetId);
    if (fromIdx === -1 || toIdx === -1) return;
    const [moved] = newOrder.splice(fromIdx, 1);
    newOrder.splice(toIdx, 0, moved);
    setCollections(newOrder);

    try {
      await reorderCollections(newOrder.map((c) => c.collection_id));
    } catch (err) {
      console.error(err);
      setCollections(prevOrder);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Collections</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create shared chart sets here. Your coauthor can review them later.
          </p>
        </div>
        {!loading && collections.length > 0 && (
          <span className="text-sm text-muted-foreground">
            {collections.length} collection{collections.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <div className="border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Plus className="h-4 w-4" /> New collection
          </div>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Collection name"
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            rows={4}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button
            onClick={handleCreate}
            disabled={saving || !name.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Bookmark className="h-4 w-4" /> Create collection
          </button>
        </div>

        <div className="border rounded-xl p-4 bg-muted/20">
          <div className="text-sm font-medium mb-2">How this works</div>
          <p className="text-sm text-muted-foreground">
            Keep the dataset directory shared so both of you see the same images. If you want private experiment runs,
            give each person a separate outputs directory or separate backend instance.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : collections.length === 0 ? (
        <div className="border rounded-xl p-12 text-center space-y-3">
          <Bookmark className="h-8 w-8 text-muted-foreground mx-auto" />
          <p className="text-sm font-medium">No collections yet</p>
          <p className="text-xs text-muted-foreground max-w-xs mx-auto">
            Browse any dataset, switch to select mode, pick charts, and save them as a collection.
          </p>
          <Link
            href="/datasets"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-2"
          >
            <Plus className="h-3.5 w-3.5" /> Browse datasets
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((col) => (
            <div
              key={col.collection_id}
              draggable={editingId !== col.collection_id}
              onDragStart={() => setDraggedId(col.collection_id)}
              onDragOver={(e) => handleDragOver(e, col.collection_id)}
              onDragLeave={() => setDragOverId((prev) => (prev === col.collection_id ? null : prev))}
              onDrop={(e) => handleDrop(e, col.collection_id)}
              onDragEnd={() => { setDraggedId(null); setDragOverId(null); }}
              className={`border rounded-xl overflow-hidden hover:shadow-md transition-shadow ${
                draggedId === col.collection_id ? "opacity-40" : ""
              } ${dragOverId === col.collection_id ? "ring-2 ring-primary" : ""}`}
            >
              <Link href={`/collections/${col.collection_id}`} draggable={false} className="block p-4">
                <div className="flex items-start gap-3">
                  <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0 mt-1 cursor-grab" />
                  <Bookmark className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    {editingId === col.collection_id ? (
                      <div className="flex items-center gap-1.5" onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
                        <input
                          autoFocus
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveEdit(col.collection_id);
                            if (e.key === "Escape") cancelEdit();
                          }}
                          className="w-full text-sm font-semibold border-b border-primary bg-transparent outline-none"
                        />
                        <button onClick={() => saveEdit(col.collection_id)} className="text-green-600 hover:text-green-700 shrink-0">
                          <Check className="h-4 w-4" />
                        </button>
                        <button onClick={cancelEdit} className="text-muted-foreground hover:text-foreground shrink-0">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 group/name">
                        <div className="font-semibold text-sm truncate">{col.name}</div>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); startEdit(col); }}
                          className="text-muted-foreground hover:text-foreground shrink-0 opacity-0 group-hover/name:opacity-100 transition-opacity"
                          title="Rename collection"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                    {col.description && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{col.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <span>{col.chart_ids.length} chart{col.chart_ids.length !== 1 ? "s" : ""}</span>
                      <span>·</span>
                      <span>{new Date(col.updated_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              </Link>
              <div className="border-t px-4 py-2 flex items-center justify-between bg-muted/20">
                <Link
                  href={`/collections/${col.collection_id}`}
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Open <ChevronRight className="h-3 w-3" />
                </Link>
                <button
                  onClick={() => handleDelete(col.collection_id, col.name)}
                  className="p-1 text-muted-foreground hover:text-destructive transition-colors"
                  title="Delete collection"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
