# How to rebuild

Main file: `src/main.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc main.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: figures/psi_delta.png, jcsa.cls, main.tex
- PDF fonts: URAEZQ+CMBX12(emb), FQYRLT+CMR10(emb), NXJFZN+CMTI9(emb)

| package | date | version |
|---|---|---|
| amsbsy | 1999/11/29 | v1.2d Bold Symbols |
| amsmath | 2025/07/09 | v2.17z AMS math features |
| amsopn | 2022/04/08 | v2.04 operator names |
| amstext | 2024/11/17 | v2.01 AMS text |
| epstopdf-base | 2020-01-24 | v2.11 Base part for package epstopdf |
| graphics | 2024/08/06 | v1.4g Standard LaTeX Graphics (DPC,SPQR) |
| graphicx | 2024/12/31 | v1.2e Enhanced LaTeX Graphics (DPC,SPQR) |
| grfext | 2019/12/03 | v1.3 Manage graphics extensions (HO) |
| iftex | 2024/12/12 | v1.0g TeX engine tests |
| infwarerr | 2019/12/03 | v1.5 Providing info/warning/error messages (HO) |
| keyval | 2022/05/29 | v1.15 key=value parser (DPC) |
| kvdefinekeys | 2019-12-19 | v1.6 Define keys (HO) |
| kvoptions | 2022-06-15 | v3.15 Key value format for package options (HO) |
| kvsetkeys | 2022-10-05 | v1.19 Key value parser (HO) |
| ltxcmds | 2023-12-04 | v1.26 LaTeX kernel commands for general use (HO) |
| pdftexcmds | 2020-06-27 | v0.33 Utility functions of pdfTeX for LuaTeX (HO) |
| trig | 2023/12/02 | v1.11 sin cos tan (DPC) |
