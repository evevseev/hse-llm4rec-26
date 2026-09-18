# A01 - Random Lunch Generator: find and fix the broken images

Starter code and prompt from the course: [original/](original) ([dryjins/RecSys-LLMs/week1](https://github.com/dryjins/RecSys-LLMs/tree/main/week1)).

**Error.** 3 of 12 dishes (Ramen, Pasta, Soup) show no picture: their Font Awesome names `fa-bowl-hot`, `fa-pasta`,
`fa-bowl` do not exist in Font Awesome Free 6.4.0, which the page loads. No console error, just an empty space.
**Cause in the prompt.** The README in the prompt only says "Icons provided by Font Awesome": no version, no Free/Pro,
no rule that names must exist, so the model wrote names from memory. (The prompt's README also lists
`style.css`/`script.js`/`assets/`, while the code is a single file.)

**Fix.** [fixed/prompt.md](fixed/prompt.md) (diff vs original: `diff original/prompt.md fixed/prompt.md`) requires
Font Awesome Free 6.4.0 and checking every name against its stylesheet. The starter `index.html` + fixed prompt were
sent to GPT-5.6 Luna through opencode; the agent downloaded the CSS and grepped each name (see `fixed/iter1/*.log`).
Result [index.html](index.html) = `fixed/iter1/run3.html`, a 4-line change of the starter code.

| Page | Dishes with a picture |
|---|---|
| original/index.html | 9 / 12 |
| fixed, iteration 1 (runs 1-3) | 12 / 12 in every run |
| fixed, iteration 2 (runs 1-3, "different icon per dish, dishes may change") | 12 / 12, but menu drifts to Cookie/Cake/Egg |

The scripts under `eval/` were generated with Claude Code for this assignment and then used to produce the saved
results. Each script also includes this note in its header or module docstring.

## Reproduce
```bash
eval/run_opencode.sh fixed/iter1/full_prompt.md out.html      # needs opencode
uv run eval/check_all_dishes.py original/index.html           # shows each of the 12 dishes in Chrome
uv run eval/check_all_dishes.py index.html
```
