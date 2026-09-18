# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.55.0", "emoji==2.14.1", "requests==2.32.3"]
# ///
"""Check whether every "image" referenced by a generated lunch-generator page actually renders.

An image reference is one of:
  * a Font Awesome icon class (e.g. "fas fa-pizza-slice")  -> rendered in headless Chrome using the
    page's own stylesheet; counts as OK only if the ::before pseudo-element has glyph content and a
    non-zero width;
  * a Unicode emoji                                          -> OK if it is a fully-qualified RGI emoji;
  * an external image URL                                    -> OK if GET returns 200 with image/* type.

Usage: uv run check_images.py FILE.html [FILE.html ...] --out results.jsonl
"""

import argparse
import json
import re
import sys
from pathlib import Path

import emoji
import requests
from playwright.sync_api import sync_playwright

# FA classes that are modifiers / style prefixes, not icons.
FA_MODIFIERS = {
    "solid", "regular", "brands", "light", "thin", "duotone", "sharp", "classic",
    "fw", "xs", "sm", "lg", "xl", "2xs", "xxs", "1x", "2x", "3x", "4x", "5x", "6x", "7x", "8x",
    "9x", "10x", "spin", "pulse", "spin-pulse", "spin-reverse", "beat", "beat-fade", "bounce",
    "fade", "flip", "shake", "border", "inverse", "li", "ul", "stack", "stack-1x", "stack-2x",
    "pull-left", "pull-right", "rotate-90", "rotate-180", "rotate-270", "rotate-by",
    "flip-horizontal", "flip-vertical", "flip-both", "layers", "layers-text", "layers-counter",
}
FA_TOKEN = re.compile(r"(?<![\w-])fa-([a-z0-9]+(?:-[a-z0-9]+)*)(?![\w-])")
URL = re.compile(r"https?://[^\s\"'`)<>]+")
NON_IMAGE_URL = re.compile(r"\.(css|js|woff2?|ttf)(\?|$)|fonts\.googleapis|fonts\.gstatic|github\.(com|io)|shields\.io|opensource\.org|w3\.org")


def fa_class_strings(html: str) -> dict[str, str]:
    """Map icon name -> a full class string it appears in (so the browser test uses the same prefix)."""
    found: dict[str, str] = {}
    for m in FA_TOKEN.finditer(html):
        name = m.group(1)
        if name in FA_MODIFIERS or name in found:
            continue
        # take the surrounding quoted string, e.g. "fas fa-pizza-slice"
        start = max(html.rfind(q, 0, m.start()) for q in "\"'`")
        end_candidates = [i for i in (html.find(q, m.end()) for q in "\"'`") if i != -1]
        end = min(end_candidates) if end_candidates else m.end()
        cls = html[start + 1:end] if 0 <= start and end - start < 200 else f"fa-solid fa-{name}"
        cls = re.sub(r"\$\{[^}]*\}", "", cls)
        if not re.search(r"\b(fa-solid|fa-regular|fa-brands|fas|far|fab|fa)\b", cls):
            cls = "fa-solid " + cls
        found[name] = " ".join(cls.split())
    # icons stored without the prefix and joined in a template:  icon: "pizza-slice" + `fa-${icon}`
    if re.search(r"fa-\$\{", html):
        for name in re.findall(r"icon\s*:\s*[\"']([a-z0-9-]+)[\"']", html):
            found.setdefault(name, f"fa-solid fa-{name}")
    return found


def browser_check(page, path: Path, classes: dict[str, str]) -> tuple[dict[str, dict], list[str]]:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(path.resolve().as_uri(), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    res = page.evaluate(
        """async (classes) => {
            const out = {};
            const box = document.createElement('div');
            document.body.appendChild(box);
            for (const [name, cls] of Object.entries(classes)) {
                const i = document.createElement('i');
                i.className = cls;
                box.appendChild(i);
            }
            await document.fonts.ready;
            await new Promise(r => setTimeout(r, 300));
            let k = 0;
            for (const [name, cls] of Object.entries(classes)) {
                const i = box.children[k++];
                const st = getComputedStyle(i, '::before');
                out[name] = {cls, content: st.content, font: st.fontFamily, width: i.getBoundingClientRect().width};
            }
            box.remove();
            return out;
        }""",
        classes,
    )
    for r in res.values():
        r["ok"] = r["content"] not in ("none", "normal", '""', "") and r["width"] > 0
    return res, errors


def url_check(url: str) -> dict:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        ctype = r.headers.get("content-type", "")
        return {"status": r.status_code, "type": ctype, "ok": r.status_code == 200 and ctype.startswith("image/")}
    except requests.RequestException as e:
        return {"status": None, "type": str(e)[:80], "ok": False}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with sync_playwright() as p, args.out.open("w") as out:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for f in args.files:
            html = f.read_text()
            classes = fa_class_strings(html)
            ctx = browser.new_context()
            page = ctx.new_page()
            fa, errors = browser_check(page, f, classes) if classes else ({}, [])
            ctx.close()
            emojis = sorted({e["emoji"] for e in emoji.emoji_list(html)})
            emoji_res = {e: {"ok": emoji.is_emoji(e)} for e in emojis}
            urls = sorted({u for u in URL.findall(html) if not NON_IMAGE_URL.search(u)})
            url_res = {u: url_check(u) for u in urls}
            refs = [*fa.values(), *emoji_res.values(), *url_res.values()]
            rec = {
                "file": str(f),
                "n_fa": len(fa), "n_emoji": len(emoji_res), "n_url": len(url_res),
                "n_refs": len(refs), "n_broken": sum(not r["ok"] for r in refs),
                "broken_fa": sorted(k for k, v in fa.items() if not v["ok"]),
                "broken_url": sorted(k for k, v in url_res.items() if not v["ok"]),
                "console_errors": errors,
                "fa": fa, "emoji": emoji_res, "url": url_res,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{f}: refs={rec['n_refs']} (fa={rec['n_fa']} emoji={rec['n_emoji']} url={rec['n_url']}) "
                  f"broken={rec['n_broken']} {rec['broken_fa'] + rec['broken_url']}", file=sys.stderr)
        browser.close()


if __name__ == "__main__":
    main()
