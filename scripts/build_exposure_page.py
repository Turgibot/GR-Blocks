"""Build the self-contained page safe-exposure.html (an extension, separate from the paper's workbench).

usage: python3 scripts/build_exposure_page.py       needs out/exposure_<WORD>.json (scripts/make_exposure.py) and docs/safe_exposure.md
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEFAULT = "MASTER"


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)


def md_to_html(md):
    """Just enough Markdown for docs/safe_exposure.md: ## heading, paragraphs, indented formula lines, pipe tables."""
    out, para, rows = [], [], []

    def flush():
        nonlocal para, rows
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if rows:
            head, *body = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|[\s\-|]+\|$", r)]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
            rows = []

    for ln in md.splitlines():
        if ln.startswith("## "):
            flush(); out.append(f"<h3>{inline(ln[3:])}</h3>")
        elif ln.startswith("|"):
            if para:
                flush()
            rows.append(ln)
        elif ln.startswith("  ") and ln.strip():
            flush(); out.append(f'<div class="formula">{inline(ln.strip())}</div>')
        elif not ln.strip():
            flush()
        else:
            if rows:
                flush()
            para.append(ln.strip())
    flush()
    return "\n".join(out)


words = {}
for path in sorted(OUT.glob("exposure_*.json")):
    words[path.stem.split("_", 1)[1]] = json.loads(path.read_text())
assert DEFAULT in words, "out/exposure_MASTER.json is missing (run scripts/make_exposure.py)"
trace = json.loads((OUT / f"trace_{DEFAULT}.json").read_text())
order = [w for w in trace["meta"]["words"] if w in words]
data = {"default": DEFAULT, "order": order, "words": words, "n_goals": len(trace["meta"]["words"]),
        "blocks": sorted(b for t in trace["meta"]["start_towers"] for b in t)}

page = (ROOT / "viewer" / "exposure_template.html").read_text()
assert "/*DATA_JSON*/null" in page and "/*TEXT_HTML*/" in page
text = md_to_html((ROOT / "docs" / "safe_exposure.md").read_text())
out = ROOT / "safe-exposure.html"
out.write_text(page.replace("/*TEXT_HTML*/", text).replace("/*DATA_JSON*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
print(f"wrote {out.name}: {len(order)} goal word(s) ({', '.join(order)}), {out.stat().st_size / 1024:.0f} KB")
