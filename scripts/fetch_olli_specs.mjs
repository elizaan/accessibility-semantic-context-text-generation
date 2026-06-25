#!/usr/bin/env node
/**
 * Fetch all Olli gallery Vega-Lite specs from GitHub and save to
 * data/olli/raw_specs.json
 *
 * Run from repo root:
 *   node scripts/fetch_olli_specs.mjs
 *
 * No npm dependencies needed — uses built-in fetch (Node 18+).
 */

import { writeFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT   = join(__dir, "..");
const OUT    = join(ROOT, "data", "olli", "raw_specs.json");

const GITHUB_API =
  "https://api.github.com/repos/umwelt-data/olli/contents/apps/docs/gallery/examples/vega-lite";
const RAW_BASE =
  "https://raw.githubusercontent.com/umwelt-data/olli/main/apps/docs/gallery/examples/vega-lite";

// ─── Chart type map from Vega-Lite mark → our schema ─────────────────────────
const MARK_TO_TYPE = {
  bar:    "bar",
  line:   "line",
  area:   "line",
  point:  "scatter",
  circle: "scatter",
  square: "scatter",
  tick:   "scatter",   // strip plot
  rect:   "heatmap",
  arc:    "bar",       // pie/donut — closest in our schema
  rule:   "line",
};

// ─── Detect mark from a Vega-Lite spec (handles layered/concat/facet too) ────
function detectMark(spec) {
  if (spec.mark) {
    const m = typeof spec.mark === "string" ? spec.mark : spec.mark.type;
    return MARK_TO_TYPE[m] ?? "bar";
  }
  if (spec.layer)  return detectMark(spec.layer[0]);
  if (spec.concat) return detectMark(spec.concat[0]);
  if (spec.hconcat)return detectMark(spec.hconcat[0]);
  if (spec.vconcat)return detectMark(spec.vconcat[0]);
  if (spec.spec)   return detectMark(spec.spec);
  return "bar";
}

// ─── Strip TypeScript wrapper and eval the object literal ────────────────────
function parseTypescript(src) {
  const js = src
    .replace(/import[^\n]+\n/g, "")                     // remove import lines
    .replace(/export\s+const\s+\w+\s*:\s*[\w.]+\s*=\s*/, "") // remove export declaration
    .trimEnd()
    .replace(/;$/, "");                                  // remove trailing semicolon

  // Use Function constructor to safely eval the object literal
  return new Function("return (" + js + ")")();
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log("Fetching gallery file list from GitHub API…");
  const listRes  = await fetch(GITHUB_API, {
    headers: { "User-Agent": "accessviz-benchmark" },
  });
  const files    = await listRes.json();
  const tsFiles  = files.filter((f) => f.name.endsWith(".ts"));
  console.log(`  Found ${tsFiles.length} TypeScript spec files`);

  const specs = [];
  let ok = 0, failed = 0;

  for (const file of tsFiles) {
    const url  = `${RAW_BASE}/${file.name}`;
    const res  = await fetch(url, { headers: { "User-Agent": "accessviz-benchmark" } });
    const text = await res.text();

    try {
      const obj      = parseTypescript(text);
      const chartType = detectMark(obj.spec ?? {});

      // Extract title from spec if missing from obj
      const title = obj.title
        ?? obj.spec?.title
        ?? obj.id.replace(/-/g, " ");

      specs.push({
        id:          obj.id,
        title,
        description: obj.description ?? null,
        chart_type:  chartType,
        vl_spec:     obj.spec ?? null,
      });

      console.log(`  ✓  ${file.name}  →  ${chartType}`);
      ok++;
    } catch (e) {
      console.warn(`  ✗  ${file.name}: ${e.message}`);
      failed++;
    }
  }

  mkdirSync(join(ROOT, "data", "olli"), { recursive: true });
  writeFileSync(OUT, JSON.stringify(specs, null, 2));
  console.log(`\nSaved ${ok} specs to ${OUT}  (${failed} failed)`);
}

main().catch((e) => { console.error(e); process.exit(1); });
