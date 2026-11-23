# How to rebuild

Main file: `src/thesis.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape thesis.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape thesis.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc thesis.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "report", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: chapters/ch03.tex, chapters/ch1.tex, chapters/ch2.tex, thesis.tex
- PDF fonts: VHSOMK+CMBX12(emb), ZIUKPZ+CMR12(emb), ZZFHLP+CMMI12(emb), JWMRPD+CMMI8(emb), ZOXCTA+CMSY10(emb), PXOHER+CMR8(emb)

| package | date | version |
|---|---|---|
| amsbsy | 1999/11/29 | v1.2d Bold Symbols |
| amsmath | 2025/07/09 | v2.17z AMS math features |
| amsopn | 2022/04/08 | v2.04 operator names |
| amstext | 2024/11/17 | v2.01 AMS text |
| array | 2025/09/25 | v2.6n Tabular extension package (FMi) |
| bigintcalc | 2019/12/15 | v1.5 Expandable calculations on big integers (HO) |
| bitset | 2019/12/09 | v1.3 Handle bit-vector datatype (HO) |
| cleveref | 2018/03/27 | v0.21.4 Intelligent cross-referencing |
| colortbl | 2024/10/29 | v1.0k Color table columns (DPC) |
| epstopdf-base | 2020-01-24 | v2.11 Base part for package epstopdf |
| etoolbox | 2025/10/02 | v2.5m e-TeX tools for LaTeX (JAW) |
| gettitlestring | 2019/12/15 | v1.6 Cleanup title references (HO) |
| graphics | 2024/08/06 | v1.4g Standard LaTeX Graphics (DPC,SPQR) |
| graphicx | 2024/12/31 | v1.2e Enhanced LaTeX Graphics (DPC,SPQR) |
| hycolor | 2020-01-27 | v1.10 Color options for hyperref/bookmark (HO) |
| hyperref | 2026-04-24 | v7.01q Hypertext links for LaTeX |
| iftex | 2024/12/12 | v1.0g TeX engine tests |
| infwarerr | 2019/12/03 | v1.5 Providing info/warning/error messages (HO) |
| intcalc | 2019/12/15 | v1.3 Expandable calculations with integers (HO) |
| keyval | 2022/05/29 | v1.15 key=value parser (DPC) |
| kvdefinekeys | 2019-12-19 | v1.6 Define keys (HO) |
| kvoptions | 2022-06-15 | v3.15 Key value format for package options (HO) |
| kvsetkeys | 2022-10-05 | v1.19 Key value parser (HO) |
| ltxcmds | 2023-12-04 | v1.26 LaTeX kernel commands for general use (HO) |
| nameref | 2026-01-29 | v2.58 Cross-referencing by name of section |
| pdfescape | 2019/12/09 | v1.15 Implements pdfTeX's escape features (HO) |
| pdftexcmds | 2020-06-27 | v0.33 Utility functions of pdfTeX for LuaTeX (HO) |
| pgf | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgfcomp-version-0-65 | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgfcomp-version-1-18 | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgfcore | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgffor | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgfrcs | 2025-08-29 | v3.1.11a (3.1.11a) |
| pgfsys | 2025-08-29 | v3.1.11a (3.1.11a) |
| refcount | 2019/12/15 | v3.6 Data extraction from label references (HO) |
| rerunfilecheck | 2025-06-21 | v1.11 Rerun checks for auxiliary files (HO) |
| stringenc | 2019/11/29 | v1.12 Convert strings between diff. encodings (HO) |
| tikz | 2025-08-29 | v3.1.11a (3.1.11a) |
| trig | 2023/12/02 | v1.11 sin cos tan (DPC) |
| uniquecounter | 2019/12/15 | v1.4 Provide unlimited unique counter (HO) |
| url | 2013/09/16 | ver 3.4  Verb mode for urls, etc. |
| xcolor | 2024/09/29 | v3.02 LaTeX color extensions (UK) |
