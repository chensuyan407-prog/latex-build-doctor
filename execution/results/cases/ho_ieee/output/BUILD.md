# How to rebuild

Main file: `src/conf.tex` - engine **pdflatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape conf.tex
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape conf.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc conf.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
- bib tool: none
- document class: {"name": "IEEEtran", "date": "2015/08/26", "version": "V1.8b by Michael Shell"}
- project files read by TeX: conf.tex
- PDF fonts: RQBWDV+NimbusRomNo9L-Regu(emb), QVCFWU+NimbusRomNo9L-MediItal(emb), NOKVZV+NimbusRomNo9L-Medi(emb)

| package | date | version |
|---|---|---|
| algorithm | 2009/08/24 | v0.1 Document Style `algorithm' - floating environment |
| algorithmic | 2009/08/24 | v0.1 Document Style `algorithmic' |
| caption | 2023/08/05 | v3.6o Customizing captions (AR) |
| caption3 | 2023/07/31 | v2.4d caption3 kernel (AR) |
| epstopdf-base | 2020-01-24 | v2.11 Base part for package epstopdf |
| float | 2001/11/08 | v1.3d Float enhancements (AL) |
| graphics | 2024/08/06 | v1.4g Standard LaTeX Graphics (DPC,SPQR) |
| graphicx | 2024/12/31 | v1.2e Enhanced LaTeX Graphics (DPC,SPQR) |
| ifthen | 2024/03/16 | v1.1e Standard LaTeX ifthen package (DPC) |
| keyval | 2022/05/29 | v1.15 key=value parser (DPC) |
| subcaption | 2023/07/28 | v1.6b Sub-captions (AR) |
| trig | 2023/12/02 | v1.11 sin cos tan (DPC) |
