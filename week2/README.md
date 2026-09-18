# A01 — Random Lunch Generator: fixing the images

Teacher's version ([original/](original)) shows **no picture** for 3 of 12 dishes (Ramen, Pasta, Soup):
it uses Font Awesome icons `fa-bowl-hot`, `fa-pasta`, `fa-bowl`, which do not exist in Font Awesome Free 6.4.0.
The browser fails silently — no error in the console, just an empty space.

Fix: change the prompt ([prompts/p1_emoji.md](prompts/p1_emoji.md)) so the model draws every dish with a standard
Unicode emoji instead of an icon font, and must replace a dish if there is no emoji for it.

| Page | Model | Images | Broken |
|---|---|---|---|
| original/index.html (teacher) | unknown | 16 FA icons | **3** |
| runs/p0_run1..3 (original prompt) | gpt-5.6-luna via opencode | 11–12 emoji | 0 |
| runs/p1_run1..3 (fixed prompt) | gpt-5.6-luna via opencode | 16–17 emoji | 0 |

`index.html` = `runs/p1_run1.html` (unchanged model output).

## Reproduce

```bash
eval/run_opencode.sh prompts/p1_emoji.md runs/new.html          # generate (needs opencode)
uv run eval/check_images.py original/index.html runs/*.html --out results/check.jsonl   # check images in Chrome
```
