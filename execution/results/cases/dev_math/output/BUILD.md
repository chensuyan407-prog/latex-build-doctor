# How to rebuild

Main file: `src/model.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape model.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape model.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc model.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: model.tex
- PDF fonts: HWPSOU+CMBX12(emb), WYULUG+CMR10(emb), FHCKNB+CMMI10(emb), BXEDEJ+CMMI7(emb), GSXYAU+CMEX10(emb), MAXHKX+CMR7(emb), JESHKV+CMSY10(emb), QDTWCG+MSBM10(emb)

| package | date | version |
|---|---|---|
| amsbsy | 1999/11/29 | v1.2d Bold Symbols |
| amsfonts | 2013/01/14 | v3.01 Basic AMSFonts support |
| amsmath | 2025/07/09 | v2.17z AMS math features |
| amsopn | 2022/04/08 | v2.04 operator names |
| amssymb | 2013/01/14 | v3.01 AMS font symbols |
| amstext | 2024/11/17 | v2.01 AMS text |
