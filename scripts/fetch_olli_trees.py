#!/usr/bin/env python3
"""
Scrape Olli ARIA trees from the Olli gallery and patch data/olli/charts.json.

Each gallery page at https://umwelt-data.github.io/olli/gallery/<slug>/
renders a [role="tree"] element — the full Olli screen-reader navigation tree.
We extract its inner text and store it in chart.metadata.olli_tree.

Prerequisites (one-time):
  backend/.venv/bin/pip install playwright
  backend/.venv/bin/python -m playwright install chromium

Run from repo root:
  backend/.venv/bin/python scripts/fetch_olli_trees.py
"""

from __future__ import annotations
import asyncio
import json
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit(
        "playwright not installed.\n"
        "Run: backend/.venv/bin/pip install playwright\n"
        "     backend/.venv/bin/python -m playwright install chromium"
    )

ROOT = Path(__file__).parent.parent
CHARTS_JSON = ROOT / "data" / "olli" / "charts.json"
GALLERY_BASE = "https://umwelt-data.github.io/olli/gallery"

# Some chart IDs in our data differ from the gallery slug — map them here
SLUG_OVERRIDES: dict[str, str] = {
    "concat-chart": "concat-chart",  # gallery uses concat-chart
    "boxplot":      "boxplot",       # our data may have box_plot
}


def chart_id_to_slug(chart_id: str) -> str:
    raw = chart_id.removeprefix("olli_")
    return SLUG_OVERRIDES.get(raw, raw)


_CLEAN = [
    "Press ? for help.",
    "Press t to open table.",
    "Press enter to select.",
]

_EXTRACT_JS = """() => {
    function depth(el) {
        let d = 0, p = el.parentElement;
        while (p) {
            const r = p.getAttribute('role');
            if (r === 'tree' || r === 'group') d++;
            p = p.parentElement;
        }
        return d;
    }
    return [...document.querySelectorAll('[role="treeitem"]')].map(el => ({
        depth: depth(el),
        text: (el.getAttribute('aria-label') || el.firstChild?.textContent || '').trim()
    }));
}"""


def _build_tree_text(items: list[dict]) -> str:
    lines = []
    for item in items:
        text = item["text"]
        for hint in _CLEAN:
            text = text.replace(hint, "").strip()
        if text:
            lines.append("  " * item["depth"] + text)
    return "\n".join(lines)


async def scrape_tree(page, slug: str, retries: int = 2) -> str | None:
    url = f"{GALLERY_BASE}/{slug}/"
    for attempt in range(retries + 1):
        try:
            await page.goto(url, wait_until="networkidle", timeout=20_000)
            await page.wait_for_selector('[role="tree"]', timeout=10_000)
            items = await page.evaluate(_EXTRACT_JS)
            if items:
                return _build_tree_text(items)
        except PWTimeout:
            if attempt < retries:
                print(f"    Timeout, retrying ({attempt + 1}/{retries})…")
                await page.wait_for_timeout(2000)
            else:
                print(f"    Timed out after {retries + 1} attempts.")
        except Exception as e:
            print(f"    Error: {e}")
            break
    return None


async def main() -> None:
    charts: list[dict] = json.loads(CHARTS_JSON.read_text(encoding="utf-8"))
    total = len(charts)
    already = sum(1 for c in charts if c["metadata"].get("olli_tree"))
    print(f"Olli charts: {total}  |  already have tree: {already}  |  to scrape: {total - already}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        updated = 0
        for chart in charts:
            if chart["metadata"].get("olli_tree"):
                print(f"  ✓ skip  {chart['chart_id']} (already populated)")
                continue

            slug = chart_id_to_slug(chart["chart_id"])
            print(f"  → {chart['chart_id']:40s}  slug={slug}")
            tree_text = await scrape_tree(page, slug)

            if tree_text:
                chart["metadata"]["olli_tree"] = tree_text
                updated += 1
                preview = tree_text[:80].replace("\n", " ")
                print(f"    ✓ {len(tree_text)} chars  |  {preview!r}")
            else:
                print(f"    ✗ no tree found — leaving as null")

        await browser.close()

    CHARTS_JSON.write_text(json.dumps(charts, indent=2, ensure_ascii=False))
    print(f"\nDone. Updated {updated}/{total - already} charts.")
    print(f"Written → {CHARTS_JSON}")


if __name__ == "__main__":
    asyncio.run(main())
