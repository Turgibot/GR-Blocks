"""Build the self-contained calculation page: viewer/calc_template.html + out/trace_<WORD>.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
page = (ROOT / "viewer" / "calc_template.html").read_text()
assert "/*TRACE_JSON*/null" in page
data = json.dumps(trace, separators=(",", ":")).replace("</", "<\\/")      # never close the script tag early
out = ROOT / "recognition-calculations.html"
out.write_text(page.replace("/*TRACE_JSON*/null", data))
print(f"wrote {out.name}  ({out.stat().st_size / 1024:.0f} KB)")
