# How to rebuild

Main file: `src/main.tex` - engine **xelatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc main.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: XeTeX 3.141592653-2.6-0.999998 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: main.tex
- PDF fonts: QVIUWV+LMRoman10-Regular-Identity-H(emb)

| package | date | version |
|---|---|---|
| expl3 | 2026-03-20 | L3 programming layer (loader) |
| fontenc | 2025/07/18 | v2.1d Standard LaTeX package |
| fontspec | 2025/09/29 | v2.9g Font selection for XeLaTeX and LuaLaTeX |
| fontspec-xetex | 2025/09/29 | v2.9g Font selection for XeLaTeX and LuaLaTeX |
| xparse | 2025-10-09 | L3 Experimental document command parser |
