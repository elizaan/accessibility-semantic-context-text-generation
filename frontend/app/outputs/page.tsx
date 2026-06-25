"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAllOutputs } from "@/lib/api";
import { LLM_MODELS } from "@/lib/types";
import type { GenerationOutput } from "@/lib/types";
import { OutputList } from "@/components/output/OutputList";
import { Clock, Cpu, Filter } from "lucide-react";

export default function OutputsPage() {
  const [outputs, setOutputs] = useState<GenerationOutput[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [modelFilter, setModelFilter] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    getAllOutputs({ model_id: modelFilter === "all" ? undefined : modelFilter, page_size: 50 })
      .then((res) => {
        setOutputs(res.outputs);
        setTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [modelFilter]);

  const totalTokens = outputs.reduce(
    (acc, o) => acc + o.tokens_used.input + o.tokens_used.output,
    0
  );
  const avgLatency =
    outputs.length > 0
      ? outputs.reduce((acc, o) => acc + o.latency_ms, 0) / outputs.length
      : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">All Outputs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {total} generation{total !== 1 ? "s" : ""} saved · {totalTokens.toLocaleString()} total tokens · avg {(avgLatency / 1000).toFixed(1)}s
          </p>
        </div>
        <Link href="/compare" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          Compare side-by-side →
        </Link>
      </div>

      {/* Model filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <button
          onClick={() => setModelFilter("all")}
          className={`px-3 py-1.5 text-sm rounded-full border transition-colors ${modelFilter === "all" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
        >
          All models
        </button>
        {LLM_MODELS.map((m) => (
          <button
            key={m.model_id}
            onClick={() => setModelFilter(m.model_id)}
            className={`px-3 py-1.5 text-sm rounded-full border transition-colors ${modelFilter === m.model_id ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
          >
            {m.display_name}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-muted-foreground text-sm">Loading outputs…</div>
      ) : (
        <OutputList outputs={outputs} chart={null as never} />
      )}
    </div>
  );
}
