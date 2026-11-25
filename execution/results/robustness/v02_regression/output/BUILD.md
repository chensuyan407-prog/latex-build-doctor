# How to rebuild

Main file: `src/main.tex` - engine **pdflatex**, bibliography with **bibtex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
bibtex main
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc main.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: BibTeX 0.99e (TeX Live 2026)
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: main.tex
- PDF fonts: NDXQWY+CMR10(emb), TCMTMT+CMTT10(emb), XOSQUH+CMBX10(emb), ZPGVCH+CMEX10(emb), OTQOSA+CMBX12(emb), DWLMMK+CMTI10(emb)

| package | date | version |
|---|---|---|
| amsbsy | 1999/11/29 | v1.2d Bold Symbols |
| amsmath | 2025/07/09 | v2.17z AMS math features |
| amsopn | 2022/04/08 | v2.04 operator names |
| amstext | 2024/11/17 | v2.01 AMS text |
| natbib | 2010/09/13 | 8.31b (PWD, AO) |
| url | 2013/09/16 | ver 3.4  Verb mode for urls, etc. |
