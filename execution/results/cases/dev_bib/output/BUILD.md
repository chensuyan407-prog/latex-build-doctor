# How to rebuild

Main file: `src/paper.tex` - engine **pdflatex**, bibliography with **biber**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex
biber paper
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc paper.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: biber version: 2.21
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: paper.tex
- PDF fonts: MFQGJR+CMR17(emb), ZALXIT+CMR12(emb), AJEXIO+CMR10(emb), KTQSAD+CMBX10(emb), OTQOSA+CMBX12(emb), JBQLDP+CMTI10(emb)

| package | date | version |
|---|---|---|
| biblatex | 2025/07/10 | v3.21 programmable bibliographies (PK/MW) |
| bigintcalc | 2019/12/15 | v1.5 Expandable calculations on big integers (HO) |
| bitset | 2019/12/09 | v1.3 Handle bit-vector datatype (HO) |
| blx-case-expl3 | 2025/07/10 | v3.21 expl3 case changing code for biblatex |
| etoolbox | 2025/10/02 | v2.5m e-TeX tools for LaTeX (JAW) |
| expl3 | 2026-03-20 | L3 programming layer (loader) |
| gettitlestring | 2019/12/15 | v1.6 Cleanup title references (HO) |
| hycolor | 2020-01-27 | v1.10 Color options for hyperref/bookmark (HO) |
| hyperref | 2026-04-24 | v7.01q Hypertext links for LaTeX |
| iftex | 2024/12/12 | v1.0g TeX engine tests |
| ifthen | 2024/03/16 | v1.1e Standard LaTeX ifthen package (DPC) |
| infwarerr | 2019/12/03 | v1.5 Providing info/warning/error messages (HO) |
| intcalc | 2019/12/15 | v1.3 Expandable calculations with integers (HO) |
| keyval | 2022/05/29 | v1.15 key=value parser (DPC) |
| kvdefinekeys | 2019-12-19 | v1.6 Define keys (HO) |
| kvoptions | 2022-06-15 | v3.15 Key value format for package options (HO) |
| kvsetkeys | 2022-10-05 | v1.19 Key value parser (HO) |
| logreq | 2010/08/04 | v1.0 xml request logger |
| ltxcmds | 2023-12-04 | v1.26 LaTeX kernel commands for general use (HO) |
| nameref | 2026-01-29 | v2.58 Cross-referencing by name of section |
| pdfescape | 2019/12/09 | v1.15 Implements pdfTeX's escape features (HO) |
| pdftexcmds | 2020-06-27 | v0.33 Utility functions of pdfTeX for LuaTeX (HO) |
| refcount | 2019/12/15 | v3.6 Data extraction from label references (HO) |
| rerunfilecheck | 2025-06-21 | v1.11 Rerun checks for auxiliary files (HO) |
| stringenc | 2019/11/29 | v1.12 Convert strings between diff. encodings (HO) |
| uniquecounter | 2019/12/15 | v1.4 Provide unlimited unique counter (HO) |
| url | 2013/09/16 | ver 3.4  Verb mode for urls, etc. |
| xparse | 2025-10-09 | L3 Experimental document command parser |
