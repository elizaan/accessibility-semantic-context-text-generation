#!/usr/bin/env python3
"""
Fetch up to 500 Our World in Data charts for the AccessViz benchmark.

Strategy: pull chart slugs from OWID's sitemap (no guessing), then
download PNG + CSV + page metadata for each one until the target is met.

Run from repo root:
  python3 scripts/fetch_owid_charts.py [--target N]

Saves progress every 20 charts so you can resume after interruptions.
"""

from __future__ import annotations
import csv
import io
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
import collections
from pathlib import Path

try:
    import httpx
except ImportError:
    raise SystemExit("httpx not installed. Run: backend/.venv/bin/pip install httpx")

ROOT     = Path(__file__).parent.parent
OWID_DIR = ROOT / "data" / "our_world_data"
IMAGES   = OWID_DIR / "images"
OUT      = OWID_DIR / "charts.json"
IMAGES.mkdir(parents=True, exist_ok=True)

BASE    = "https://ourworldindata.org"
TARGET  = int(sys.argv[sys.argv.index("--target") + 1]) if "--target" in sys.argv else 500

HEADERS = {
    "User-Agent": "accessviz-benchmark/1.0 (academic research; contact: researcher)",
    "Accept": "text/html,application/xml,text/xml,*/*",
}

OWID_TYPE_MAP = {
    "LineChart":   "line",
    "StackedArea": "line",
    "SlopeChart":  "line",
    "DiscreteBar": "bar",
    "StackedBar":  "bar",
    "Marimekko":   "other",
    "ScatterPlot": "scatter",
    "WorldMap":    "other",
    "Choropleth":  "other",
}

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "public_health": [
        "health", "disease", "vaccine", "covid", "hospital", "mortality",
        "death", "cancer", "diabetes", "obesity", "epidemic", "pandemic",
        "life expectancy", "drug", "malaria", "hiv", "tuberculosis",
        "mental health", "alcohol", "smoking", "tobacco", "nutrition",
        "sanitation", "suicide", "injury", "respiratory",
    ],
    "climate": [
        "temperature", "emission", "carbon", "climate", "renewable", "energy",
        "pollution", "greenhouse", "co2", "fossil fuel", "electricity", "solar",
        "wind", "deforestation", "sea level", "wildfire", "drought", "plastic",
        "methane", "ozone", "nitrous oxide", "biodiversity",
    ],
    "finance": [
        "gdp", "revenue", "profit", "trade", "inflation", "price", "economic",
        "economy", "income", "tax", "investment", "debt", "budget", "spending",
        "export", "import", "poverty", "wealth", "inequality", "remittance",
        "gini", "stock market", "financial", "banking", "fiscal",
    ],
    "education": [
        "school", "university", "college", "education", "student", "literacy",
        "graduation", "degree", "academic", "enrollment", "teacher", "pisa",
        "learning", "reading", "mathematics", "tuition", "textbook", "classroom",
    ],
    "demographics": [
        "population", "birth rate", "death rate", "migration", "age group",
        "gender", "ethnicity", "urban", "rural", "household", "fertility",
        "elderly", "median age", "sex ratio", "life expectancy", "refugee",
    ],
    "employment": [
        "employment", "unemployment", "job", "labor", "labour", "workforce",
        "worker", "occupation", "industry", "productivity", "wages",
        "self-employed", "working hours", "strike", "union", "minimum wage",
    ],
}


def infer_domain(title: str, subtitle: str = "") -> str:
    text = (title + " " + subtitle).lower()
    scores = {
        d: sum(1 for kw in kws if kw in text)
        for d, kws in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] > 0 else "general"


# ─── Sitemap discovery ────────────────────────────────────────────────────────

def _parse_slugs_from_xml(xml_text: str) -> list[str]:
    slugs = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:loc", ns):
            m = re.search(r"/grapher/([^/?#\s]+)", loc.text or "")
            if m:
                slug = m.group(1)
                if not any(slug.endswith(ext) for ext in [".png", ".csv", ".json", ".svg"]):
                    slugs.append(slug)
    except ET.ParseError:
        pass
    return slugs


def fetch_all_slugs(client: httpx.Client) -> list[str]:
    """Discover chart slugs via OWID's sitemap."""
    slugs: list[str] = []

    # Find sitemap URL via robots.txt
    sitemap_candidates = [
        f"{BASE}/sitemap.xml",
        f"{BASE}/sitemap_index.xml",
    ]
    try:
        r = client.get(f"{BASE}/robots.txt", timeout=15)
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                sitemap_candidates.insert(0, url)
    except Exception:
        pass

    for sitemap_url in sitemap_candidates[:3]:
        print(f"  Trying {sitemap_url} …")
        try:
            r = client.get(sitemap_url, timeout=30)
            if r.status_code != 200:
                continue

            # Sitemap index? Follow sub-sitemaps that mention grapher/charts
            sub_urls = []
            try:
                root = ET.fromstring(r.text)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                for loc in root.findall("sm:sitemap/sm:loc", ns):
                    sub_urls.append(loc.text)
            except ET.ParseError:
                pass

            if sub_urls:
                print(f"    Sitemap index with {len(sub_urls)} sub-sitemaps")
                for sub_url in sub_urls:
                    try:
                        r2 = client.get(sub_url, timeout=30)
                        batch = _parse_slugs_from_xml(r2.text)
                        slugs.extend(batch)
                        if batch:
                            print(f"    {sub_url.split('/')[-1]}: {len(batch)} chart slugs")
                    except Exception:
                        pass
            else:
                batch = _parse_slugs_from_xml(r.text)
                slugs.extend(batch)
                print(f"    Direct sitemap: {len(batch)} chart slugs")

            if slugs:
                break

        except Exception as e:
            print(f"    Error: {e}")

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


# ─── Per-chart fetchers ───────────────────────────────────────────────────────

def fetch_metadata(client: httpx.Client, slug: str) -> dict:
    try:
        r = client.get(f"{BASE}/grapher/{slug}", follow_redirects=True, timeout=20)
        if r.status_code != 200:
            return {}
        html = r.text
        # __NEXT_DATA__ (Next.js)
        m = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if m:
            try:
                nd = json.loads(m.group(1))
                cfg = (
                    nd.get("props", {}).get("pageProps", {}).get("grapher")
                    or nd.get("props", {}).get("pageProps", {}).get("config")
                    or {}
                )
                if cfg:
                    return cfg
            except Exception:
                pass
        # OG meta fallback
        t = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
        d = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
        return {"title": t.group(1) if t else None, "subtitle": d.group(1) if d else None}
    except Exception:
        return {}


def fetch_png(client: httpx.Client, slug: str) -> str | None:
    try:
        r = client.get(f"{BASE}/grapher/{slug}.png", follow_redirects=True, timeout=30)
        if r.status_code != 200:
            return None
        (IMAGES / f"{slug}.png").write_bytes(r.content)
        return f"our_world_data/images/{slug}.png"
    except Exception:
        return None


def fetch_data_table(client: httpx.Client, slug: str) -> list[dict] | None:
    try:
        r = client.get(f"{BASE}/grapher/{slug}.csv", follow_redirects=True, timeout=30)
        if r.status_code != 200:
            return None
        rows = list(csv.DictReader(io.StringIO(r.text)))
        if not rows:
            return None
        all_years = sorted({int(row["Year"]) for row in rows if row.get("Year", "").isdigit()})
        recent    = set(all_years[-10:])
        filtered  = [
            {k: v for k, v in row.items() if k != "Code"}
            for row in rows
            if row.get("Year", "").isdigit() and int(row["Year"]) in recent
        ]
        entity_latest: dict[str, dict] = {}
        for row in filtered:
            ent  = row.get("Entity", "")
            year = int(row.get("Year", 0))
            if ent not in entity_latest or year > int(entity_latest[ent].get("Year", 0)):
                entity_latest[ent] = row
        top = sorted(entity_latest.values(), key=lambda r: r.get("Year", 0), reverse=True)[:30]
        return top or None
    except Exception:
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load existing charts (resume support)
    existing: dict[str, dict] = {}
    if OUT.exists():
        for c in json.loads(OUT.read_text()):
            existing[c["chart_id"]] = c
    print(f"Existing: {len(existing)} charts | Target: {TARGET}\n")

    charts: list[dict] = list(existing.values())
    if len(charts) >= TARGET:
        print(f"Target already reached ({len(charts)} charts).")
        return

    existing_slugs = {
        c["chart_id"].removeprefix("owid_").replace("_", "-")
        for c in charts
    }

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        # ── Step 1: get slugs from sitemap ────────────────────────────────────
        print("Discovering slugs from OWID sitemap…")
        all_slugs = fetch_all_slugs(client)
        print(f"  {len(all_slugs)} unique chart slugs found\n")

        if not all_slugs:
            print("No slugs from sitemap. Exiting.")
            return

        # Shuffle for topic variety
        rng = random.Random(42)
        rng.shuffle(all_slugs)

        # ── Step 2: download until target reached ─────────────────────────────
        needed    = TARGET - len(charts)
        ok        = 0
        failed    = 0
        attempted = 0

        for slug in all_slugs:
            if ok >= needed:
                break
            if slug in existing_slugs:
                continue

            attempted += 1
            time.sleep(0.4)   # polite rate limit

            image_path = fetch_png(client, slug)
            if not image_path:
                failed += 1
                continue

            meta       = fetch_metadata(client, slug)
            data_table = fetch_data_table(client, slug)

            title      = meta.get("title")    or slug.replace("-", " ").title()
            subtitle   = meta.get("subtitle") or None
            owid_type  = meta.get("type")     or "LineChart"
            chart_type = OWID_TYPE_MAP.get(owid_type, "line")
            domain     = infer_domain(title, subtitle or "")

            note = meta.get("note")
            domain_context = (
                f"{subtitle} {note}".strip()
                if subtitle and note and note not in subtitle
                else subtitle
            )

            charts.append({
                "chart_id": f"owid_{slug.replace('-', '_')}",
                "source":     "our_world_data",
                "chart_type": chart_type,
                "domain":     domain,
                "image_path": image_path,
                "title":      title,
                "metadata": {
                    "alt_text":            None,
                    "aria_label":          None,
                    "aria_describedby":    None,
                    "olli_tree":           None,
                    "scene_graph":         None,
                    "data_table":          data_table,
                    "vega_lite_spec":      None,
                    "l1_caption":          None,
                    "l2_caption":          None,
                    "l3_caption":          None,
                    "l4_caption":          None,
                    "domain_context":      domain_context,
                    "stakeholder_context": None,
                    "source_url":          f"https://ourworldindata.org/grapher/{slug}",
                },
                "ground_truth_description": {
                    "context": "",
                    "semantic_meaning": "",
                    "real_world_significance": "",
                },
            })
            existing_slugs.add(slug)
            ok += 1

            # Save progress every 20 charts
            if ok % 20 == 0:
                OUT.write_text(json.dumps(charts, indent=2, ensure_ascii=False))
                domain_counts = collections.Counter(c["domain"] for c in charts)
                print(
                    f"  ✓ {len(charts):3d} total  (+{ok} new) | "
                    f"attempted {attempted} | failed {failed} | "
                    f"last: {title[:45]}"
                )

    # Final save
    OUT.write_text(json.dumps(charts, indent=2, ensure_ascii=False))

    domain_counts = collections.Counter(c["domain"] for c in charts)
    has_data      = sum(1 for c in charts if c["metadata"]["data_table"])
    has_ctx       = sum(1 for c in charts if c["metadata"]["domain_context"])

    print(f"\n── Final results ──")
    print(f"  Total: {len(charts)} charts  ({ok} new this run)")
    print(f"  Attempted: {attempted}  |  Failed/no-PNG: {failed}")
    print(f"\n── Domains ──")
    for d, n in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f"  {d:20s} {n}")
    print(f"\n  data_table:     {has_data}/{len(charts)}")
    print(f"  domain_context: {has_ctx}/{len(charts)}")
    print(f"\nWrote → {OUT}")


if __name__ == "__main__":
    main()
