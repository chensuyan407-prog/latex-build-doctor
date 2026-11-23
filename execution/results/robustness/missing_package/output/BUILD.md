# How to rebuild

Main file: `src/main.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc main.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: main.tex
- PDF fonts: 

| package | date | version |
|---|---|---|
