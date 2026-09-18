# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.55.0"]
# ///
"""Generated with Claude Code to show every dish and check that its picture is drawn.

For dish k of N we pin Math.random() to (k + 0.5) / N, so Math.floor(Math.random() * N) == k,
click "Generate Lunch!", wait for the 500 ms "Thinking..." delay, then read the result card:
the dish name (.food-name) and the size of the picture (.food-icon's first child).
A picture counts as drawn if its box is wider than 1 px.

Usage: uv run check_all_dishes.py PAGE.html [--n 12] [--shots DIR]
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("page", type=Path)
ap.add_argument("--n", type=int, default=12)
ap.add_argument("--shots", type=Path)
args = ap.parse_args()

rows = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    for k in range(args.n):
        page = browser.new_page(viewport={"width": 700, "height": 820})
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.add_init_script(f"Math.random = () => ({k} + 0.5) / {args.n};")
        page.goto(args.page.resolve().as_uri(), wait_until="networkidle")
        page.click("#generateBtn")
        page.wait_for_timeout(1200)
        info = page.evaluate("""() => {
            const pic = document.querySelector('.food-icon').firstElementChild || document.querySelector('.food-icon');
            const r = pic.getBoundingClientRect();
            const before = getComputedStyle(pic, '::before').content;
            return {name: document.querySelector('.food-name').textContent.trim(),
                    picture: pic.outerHTML.slice(0, 80), width: Math.round(r.width), before};
        }""")
        info.update(index=k, drawn=info["width"] > 1, console_errors=errors)
        rows.append(info)
        if args.shots:
            args.shots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=args.shots / f"{k:02d}_{info['name'].lower()}.png")
        page.close()
    browser.close()

for r in rows:
    print(f"{r['index']:2d} {r['name']:10} {'OK     ' if r['drawn'] else 'MISSING'} width={r['width']:3d}px  {r['picture']}")
print(f"\n{sum(r['drawn'] for r in rows)}/{len(rows)} dishes show a picture; console errors: "
      f"{sum(len(r['console_errors']) for r in rows)}")
print(json.dumps(rows, ensure_ascii=False), file=open(args.page.with_suffix(".dishes.json"), "w"))
