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

- distribution: unknown
- engine: ?
- bib tool: none
- document class: null
- project files read by TeX: 
- PDF fonts: 

| package | date | version |
|---|---|---|
