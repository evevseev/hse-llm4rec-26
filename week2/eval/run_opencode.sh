#!/usr/bin/env bash
# Send a prompt file to an LLM via opencode (from an empty dir, so it only sees the prompt)
# and save the ```html block it returns.  Usage: eval/run_opencode.sh PROMPT.md OUT.html
set -euo pipefail
MODEL=${MODEL:-openai/gpt-5.6-luna}
EMPTY=$(mktemp -d)
opencode run --pure --dir "$EMPTY" -m "$MODEL" "$(cat "$1")" < /dev/null > "$2.log" 2>&1
python3 - "$2.log" "$2" "$EMPTY" <<'PY'
import re, sys
from pathlib import Path
text = open(sys.argv[1]).read()
m = re.search(r"```html\s*\n(.*?)```", text, re.S)
written = Path(sys.argv[3]) / "index.html"   # the opencode agent sometimes writes the file instead of printing it
if m:
    open(sys.argv[2], "w").write(m.group(1))
elif written.exists():
    open(sys.argv[2], "w").write(written.read_text())
    print("note: taken from the file the agent wrote")
else:
    sys.exit(f"no html in {sys.argv[1]}")
PY
echo "saved $2 ($MODEL)"
