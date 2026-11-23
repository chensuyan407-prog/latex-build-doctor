# How to rebuild

Main file: `src/main.tex` - engine **xelatex**.

## Commands (run in `src/.`, in this order)

```sh
export SOURCE_DATE_EPOCH=1704067200   # fixes PDF dates/ID -> byte-identical rebuilds
export max_print_line=10000
xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex
xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex
```

Equivalent: `cd src/. && latexmk -r ../latexmkrc main.tex` (or `sh build.sh`).

## Environment recorded at build time

- distribution: TeX Live 2026
- engine: XeTeX 3.141592653-2.6-0.999998 (TeX Live 2026)
- bib tool: none
- document class: {"name": "article", "date": "2025/01/22", "version": "v1.4n Standard LaTeX document class"}
- project files read by TeX: main.tex
- PDF fonts: QVIUWV+FandolSong-Regular-Identity-H(emb), IRQUGZ+TeXGyreTermes-Regular-Identity-H(emb), DTQSCH+TeXGyreTermes-Bold-Identity-H(emb), KONLXK+FandolSong-Bold-Identity-H(emb), VJKBIL+CMR10(emb), MIUVPK+CMMI10(emb)

| package | date | version |
|---|---|---|
| amsbsy | 1999/11/29 | v1.2d Bold Symbols |
| amsmath | 2025/07/09 | v2.17z AMS math features |
| amsopn | 2022/04/08 | v2.04 operator names |
| amstext | 2024/11/17 | v2.01 AMS text |
| booktabs | 2020/01/12 | v1.61803398 Publication quality tables |
| ctexhook | 2022/07/14 | v2.5.10 Document and package hooks (CTEX) |
| ctexpatch | 2022/07/14 | v2.5.10 Patching commands (CTEX) |
| expl3 | 2026-03-20 | L3 programming layer (loader) |
| fix-cm | 2020/11/24 | v1.1t fixes to LaTeX |
| fontenc | 2025/07/18 | v2.1d Standard LaTeX package |
| fontspec | 2025/09/29 | v2.9g Font selection for XeLaTeX and LuaLaTeX |
| fontspec-xetex | 2025/09/29 | v2.9g Font selection for XeLaTeX and LuaLaTeX |
| xeCJK | 2022/08/05 | v3.9.1 Typesetting CJK scripts with XeLaTeX |
| xparse | 2025-10-09 | L3 Experimental document command parser |
| xtemplate | 2025-10-09 | L3 Experimental prototype document functions |
| zhnumber | 2022/07/14 | v3.0 Typesetting numbers with Chinese glyphs |
