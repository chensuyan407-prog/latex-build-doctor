#!/usr/bin/env python3
"""Turn a CSV / TSV / Markdown table from the materials into a booktabs LaTeX table, values copied verbatim.

  python lx_table.py data.csv --caption "Errors of both methods." --label tab:main [--align lccc] [--width tabularx]
                     [--cols "method,rmse"] [--header "Method,RMSE"] [--float table|table*|none] [--note "..."] [--out table.tex]

Cells are escaped (& % $ # _ { } ~ ^ \\) but never rounded or reformatted; numeric columns default to 'r'
(or S with --siunitx). Prints the snippet and a source map (row/col -> input line) as a LaTeX comment block,
so every number in the table can be traced back to the input file. Needs booktabs (and tabularx / siunitx if chosen).
"""
import argparse
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lx_common import read_text

ESC = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}
NUMERIC = re.compile(r"^[-+−]?(\d+(?:[.,]\d+)*|\.\d+)(?:[eE][-+]?\d+)?%?$|^[-+]?\d+(?:\.\d+)?\s*±\s*\d+(?:\.\d+)?$")


def esc(s, keep_math):
    if keep_math and re.search(r"\$[^$]+\$", s):
        parts = re.split(r"(\$[^$]+\$)", s)
        return "".join(p if p.startswith("$") else esc(p, False) for p in parts)
    out = "".join(ESC.get(c, c) for c in s)
    return out.replace("±", r"$\pm$").replace("−", "$-$") if not keep_math else out


def read_table(path, sheet_sep=None):
    text, enc = read_text(path)
    lines = text.splitlines()
    if path.lower().endswith(".md") or (lines and lines[0].strip().startswith("|")):
        rows, src = [], []
        for i, l in enumerate(lines, 1):
            if l.strip().startswith("|"):
                cells = [c.strip() for c in l.strip().strip("|").split("|")]
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    continue
                rows.append(cells)
                src.append(i)
        return rows, src
    sep = sheet_sep or ("\t" if path.lower().endswith(".tsv") or "\t" in lines[0] else ";" if lines and lines[0].count(";") > lines[0].count(",") else ",")
    rows, src = [], []
    rd = csv.reader(io.StringIO(text), delimiter=sep)
    for i, r in enumerate(rd, 1):
        if any(c.strip() for c in r):
            rows.append([c.strip() for c in r])
            src.append(rd.line_num)
    return rows, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("--caption", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--align")
    ap.add_argument("--cols", help="comma-separated subset/order of input column names")
    ap.add_argument("--header", help="comma-separated header text to print (same count as columns)")
    ap.add_argument("--width", choices=["natural", "tabularx", "longtable"], default="natural")
    ap.add_argument("--float", default="table", choices=["table", "table*", "none"])
    ap.add_argument("--placement", default="tbp")
    ap.add_argument("--siunitx", action="store_true", help="S columns for numeric data (needs siunitx)")
    ap.add_argument("--size", default="", help="e.g. small, footnotesize")
    ap.add_argument("--note", default="")
    ap.add_argument("--keep-math", action="store_true", help="leave $...$ in cells untouched")
    ap.add_argument("--out")
    a = ap.parse_args()
    rows, src = read_table(a.table)
    if not rows:
        print("ERROR no rows in", a.table)
        return 2
    head, body, bsrc = rows[0], rows[1:], src[1:]
    idx = list(range(len(head)))
    if a.cols:
        want = [c.strip() for c in a.cols.split(",")]
        idx = []
        for w in want:
            if w not in head:
                print("ERROR column %r not in %s" % (w, head))
                return 2
            idx.append(head.index(w))
    ncol = len(idx)
    width = max(len(r) for r in rows)
    bad = [(bsrc[k], len(r)) for k, r in enumerate(body) if len(r) != len(head)]
    if width > len(head) and not a.cols:
        print("ERROR rows wider than header (%d > %d) at (line, cells): %s - would silently drop columns" % (width, len(head), bad))
        return 2
    numeric = [all(NUMERIC.match(r[i]) for r in body if i < len(r) and r[i] != "") and any(i < len(r) and r[i] for r in body) for i in idx]
    align = a.align or "".join(("X" if a.width == "tabularx" and k == 0 else ("S" if a.siunitx else "r")) if n else ("X" if a.width == "tabularx" and k == 0 else "l") for k, n in enumerate(numeric))
    hdr = [h.strip() for h in a.header.split(",")] if a.header else [head[i] for i in idx]
    if len(hdr) != ncol:
        print("ERROR --header has %d names for %d columns" % (len(hdr), ncol))
        return 2
    L = []
    if a.width == "longtable":
        L.append("\\begin{longtable}{%s}" % align)
        if a.caption:
            cap_line = "  \\caption{%s}" % a.caption + ("\\label{%s}" % a.label if a.label else "") + " \\\\"
            L.append(cap_line)
        hdr_row = "  " + " & ".join(("{%s}" % esc(h, a.keep_math)) if a.siunitx and numeric[k] else esc(h, a.keep_math) for k, h in enumerate(hdr)) + " \\\\"
        L += ["  \\toprule", hdr_row, "  \\midrule", "  \\endfirsthead",
              "  \\toprule", hdr_row, "  \\midrule", "  \\endhead",
              "  \\midrule", "  \\multicolumn{%d}{r}{\\footnotesize\\emph{Continued on next page}} \\\\" % ncol, "  \\endfoot",
              "  \\bottomrule", "  \\endlastfoot"]
        for r in body:
            L.append("  " + " & ".join(esc(r[i], a.keep_math) if i < len(r) else "" for i in idx) + " \\\\")
        L.append("\\end{longtable}")
    else:
        if a.float != "none":
            L += ["\\begin{%s}[%s]" % (a.float, a.placement), "  \\centering"]
            if a.size:
                L.append("  \\%s" % a.size)
            if a.caption:
                L.append("  \\caption{%s}" % a.caption)
            if a.label:
                L.append("  \\label{%s}" % a.label)
        env = "tabularx" if a.width == "tabularx" else "tabular"
        L.append("  \\begin{%s}%s{%s}" % (env, "{\\linewidth}" if env == "tabularx" else "", align))
        L.append("    \\toprule")
        L.append("    " + " & ".join(("{%s}" % esc(h, a.keep_math)) if a.siunitx and numeric[k] else esc(h, a.keep_math) for k, h in enumerate(hdr)) + " \\\\")
        L.append("    \\midrule")
        for r in body:
            L.append("    " + " & ".join(esc(r[i], a.keep_math) if i < len(r) else "" for i in idx) + " \\\\")
        L.append("    \\bottomrule")
        L.append("  \\end{%s}" % env)
        if a.note:
            L.append("  \\par\\smallskip{\\footnotesize %s\\par}" % a.note)
        if a.float != "none":
            L.append("\\end{%s}" % a.float)
    L.append("%% source map (lx_table.py): file %s" % os.path.basename(a.table))
    L.append("%% header <- line %d; columns %s" % (src[0], ", ".join(head[i] for i in idx)))
    for k, r in enumerate(body):
        L.append("%% row %d <- %s line %d" % (k + 1, os.path.basename(a.table), bsrc[k]))
    out = "\n".join(L) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
    print(out)
    need = ["booktabs"] + (["tabularx"] if a.width == "tabularx" else []) + (["longtable"] if a.width == "longtable" else []) + (["siunitx"] if a.siunitx else [])
    print("%% needs: \\usepackage{%s}" % ",".join(need))
    if bad:
        print("%% WARNING rows with a different number of cells than the header (line, cells): %s - check the source" % bad)
    if width > len(head):
        print("%% WARNING some rows are longer than the header")
    return 0


if __name__ == "__main__":
    sys.exit(main())
