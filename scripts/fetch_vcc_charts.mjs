#!/usr/bin/env node
/**
 * Fetch Visa Chart Components demo charts for the AccessViz benchmark.
 *
 * Sources:
 *   - Pre-committed screenshots: packages/<chart>/docs/<chart>-1.png
 *   - Accessibility props + data:  .storybook/data/recipe-data.json
 *
 * Run from repo root:
 *   node scripts/fetch_vcc_charts.mjs
 *
 * No extra npm packages needed (Node 18+ built-in fetch).
 */

import { writeFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT  = join(__dir, "..");
const OUT   = join(ROOT, "data", "vcc", "charts.json");
const IMGS  = join(ROOT, "data", "vcc", "images");

mkdirSync(IMGS, { recursive: true });
mkdirSync(join(ROOT, "data", "vcc"), { recursive: true });

const GITHUB_RAW = "https://raw.githubusercontent.com/visa/visa-chart-components/main";
const HEADERS    = { "User-Agent": "accessviz-benchmark" };

// ─── VCC chart types ──────────────────────────────────────────────────────────
// Maps: recipe-data key → { slug, label, chart_type, domain }
const CHART_TYPES = [
  { key: "barChart",         slug: "bar-chart",          label: "Bar Chart",            type: "bar",     domain: "general"     },
  { key: "clusteredBarChart",slug: "clustered-bar-chart", label: "Clustered Bar Chart",  type: "bar",     domain: "general"     },
  { key: "stackedBarChart",  slug: "stacked-bar-chart",  label: "Stacked Bar Chart",    type: "bar",     domain: "finance"     },
  { key: "lineChart",        slug: "line-chart",         label: "Line Chart",           type: "line",    domain: "finance"     },
  { key: "parallelPlot",     slug: "parallel-plot",      label: "Parallel Plot",        type: "other",   domain: "general"     },
  { key: "scatterPlot",      slug: "scatter-plot",       label: "Scatter Plot",         type: "scatter", domain: "general"     },
  { key: "heatMap",          slug: "heat-map",           label: "Heat Map",             type: "heatmap", domain: "general"     },
  { key: "circlePacking",    slug: "circle-packing",     label: "Circle Packing",       type: "other",   domain: "general"     },
  { key: "dumbellPlot",      slug: "dumbbell-plot",      label: "Dumbbell Plot",        type: "scatter", domain: "public_health"},
  { key: "alluvialDiagram",  slug: "alluvial-diagram",   label: "Alluvial Diagram",     type: "other",   domain: "general"     },
  { key: "pieChart",         slug: "pie-chart",          label: "Pie Chart",            type: "other",   domain: "general"     },
  { key: "worldMap",         slug: "world-map",          label: "World Map",            type: "other",   domain: "demographics" },
];

// ─── Fetch helpers ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url, { headers: HEADERS });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

async function fetchPNG(url, destPath) {
  const r = await fetch(url, { headers: HEADERS });
  if (!r.ok) return false;
  const buf = Buffer.from(await r.arrayBuffer());
  writeFileSync(destPath, buf);
  return true;
}

// ─── Noise keys that aren't real content ─────────────────────────────────────
const ACC_NOISE = new Set([
  "disableValidation", "elementsAreInterface", "hideTextures",
  "includeDataKeyNames", "showExperimentalTextures",
]);

// ─── Pick the story with the most filled accessibility text props ─────────────
function bestStory(stories) {
  return stories.slice().sort((a, b) => {
    const scoreA = Object.keys(a.accessibility || {}).filter((k) => !ACC_NOISE.has(k)).length;
    const scoreB = Object.keys(b.accessibility || {}).filter((k) => !ACC_NOISE.has(k)).length;
    return scoreB - scoreA;
  })[0] || {};
}

// ─── Extract data table from a recipe entry ───────────────────────────────────
function extractDataTable(story) {
  const data = story?.data;
  if (!Array.isArray(data) || data.length === 0) return null;
  return data.slice(0, 30).map((row) =>
    Object.fromEntries(
      Object.entries(row).filter(([, v]) => v !== null && v !== undefined)
    )
  );
}

// ─── Map accessibility props to benchmark metadata fields ────────────────────
function extractAccessibility(story) {
  const a = story?.accessibility || {};
  return {
    alt_text:       a.executiveSummary   || null,
    aria_label:     a.includeDataKeyNames
      ? "Dynamic — VCC generates ARIA labels with data key names at runtime"
      : "Dynamic — VCC generates ARIA labels at runtime",
    l1_caption:     a.purpose            || null,
    l2_caption:     a.contextExplanation || null,
    l3_caption:     a.structureNotes     || null,
    l4_caption:     a.longDescription    || null,
    domain_context: a.statisticalNotes   || null,
  };
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("Fetching VCC recipe-data.json from GitHub…");
  let recipeArray = [];
  try {
    recipeArray = await fetchJSON(`${GITHUB_RAW}/.storybook/data/recipe-data.json`);
    console.log(`  Loaded ${recipeArray.length} story entries`);
  } catch (e) {
    console.warn(`  Warning: ${e.message}`);
  }

  // Group stories by chart slug
  const byChart = {};
  for (const entry of recipeArray) {
    const slug = entry.chart;
    if (!byChart[slug]) byChart[slug] = [];
    byChart[slug].push(entry);
  }

  const charts = [];
  let ok = 0, failed = 0;

  for (const ct of CHART_TYPES) {
    console.log(`\n  ${ct.label}`);

    const stories = byChart[ct.slug] || [];
    const story   = bestStory(stories);
    const acc     = extractAccessibility(story);
    const table   = extractDataTable(story);

    const accCount = Object.keys(story?.accessibility || {}).filter((k) => !ACC_NOISE.has(k)).length;
    console.log(`    story: "${story?.name || "none"}"  |  data: ${table?.length ?? 0} rows  |  acc fields: ${accCount}  |  l1: ${acc.l1_caption ? "✓" : "✗"}`);

    // Fetch pre-committed screenshot PNG from GitHub
    const pngUrl   = `${GITHUB_RAW}/packages/${ct.slug}/docs/${ct.slug}-1.png`;
    const destPath = join(IMGS, `${ct.slug}.png`);
    const gotPng   = await fetchPNG(pngUrl, destPath);

    if (!gotPng) {
      console.warn(`    ✗ no screenshot at expected path`);
      failed++;
    } else {
      console.log(`    ✓ screenshot saved`);
      ok++;
    }

    charts.push({
      chart_id:   `vcc_${ct.slug.replace(/-/g, "_")}`,
      source:     "vcc",
      chart_type: ct.type,
      domain:     ct.domain,
      image_path: gotPng ? `vcc/images/${ct.slug}.png` : null,
      title:      story?.mainTitle || ct.label,
      metadata: {
        alt_text:            acc.alt_text,
        aria_label:          acc.aria_label,
        aria_describedby:    null,
        olli_tree:           null,
        scene_graph:         null,
        data_table:          table,
        vega_lite_spec:      null,
        l1_caption:          acc.l1_caption,
        l2_caption:          acc.l2_caption,
        l3_caption:          acc.l3_caption,
        l4_caption:          acc.l4_caption,
        domain_context:      acc.domain_context,
        stakeholder_context: null,
        source_url:          `https://visa.github.io/visa-chart-components/?path=/story/${ct.slug}`,
      },
      ground_truth_description: {
        context: "",
        semantic_meaning: "",
        real_world_significance: "",
      },
    });
  }

  writeFileSync(OUT, JSON.stringify(charts, null, 2));
  console.log(`\nWrote ${charts.length} charts → ${OUT}`);
  console.log(`PNG: ${ok} ok, ${failed} missing`);

  // Coverage summary
  const hasL1    = charts.filter((c) => c.metadata.l1_caption).length;
  const hasTable = charts.filter((c) => c.metadata.data_table).length;
  const hasPng   = charts.filter((c) => c.image_path).length;
  console.log(`\nCoverage:`);
  console.log(`  image_path   ${hasPng} / ${charts.length}`);
  console.log(`  data_table   ${hasTable} / ${charts.length}`);
  console.log(`  l1_caption   ${hasL1} / ${charts.length}  (from accessibility.purpose)`);
}

main().catch((e) => { console.error(e); process.exit(1); });
