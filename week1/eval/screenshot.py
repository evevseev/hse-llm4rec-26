# /// script
# dependencies = ["playwright==1.55.0"]
# ///
"""Generated with Claude Code: screenshot a page with an optionally fixed lunch choice."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

src, out = Path(sys.argv[1]), sys.argv[2]
force = sys.argv[3] if len(sys.argv) > 3 else None  # e.g. "7/12"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 700, "height": 820})
    if force:
        k, n = map(int, force.split("/"))
        pg.add_init_script(f"Math.random = () => ({k} + 0.5) / {n};")
    pg.goto(src.resolve().as_uri(), wait_until="networkidle")
    btn = pg.locator("button").first
    btn.click()
    pg.wait_for_timeout(2500)
    pg.screenshot(path=out)
    b.close()
