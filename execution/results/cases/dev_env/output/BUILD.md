# How to rebuild

Main file: `src/report.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape report.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape report.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc report.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: report.tex
- PDF fonts: WPGDNZ+CMBX12(emb), MULJMX+SFRM1000(emb), TMGULI+CMR10(emb)

| package | date | version |
|---|---|---|
| epstopdf-base | 2020-01-24 | v2.11 Base part for package epstopdf |
| graphics | 2024/08/06 | v1.4g Standard LaTeX Graphics (DPC,SPQR) |
| graphicx | 2024/12/31 | v1.2e Enhanced LaTeX Graphics (DPC,SPQR) |
| keyval | 2022/05/29 | v1.15 key=value parser (DPC) |
| trig | 2023/12/02 | v1.11 sin cos tan (DPC) |
