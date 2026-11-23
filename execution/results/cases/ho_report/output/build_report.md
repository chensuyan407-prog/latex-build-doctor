# Build report (success)

SUCCESS: main.tex with pdflatex, 3 engine pass(es) + bibtex; 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 3 edit hunk(s), 3 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `bibtex main` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: True
- PDF: main.pdf (1 pages)

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | main.tex | 7-7 | True | U+2264 not available under pdfLaTeX; same symbol in math |
| H002 | main.tex | 9-13 | True | width needs a unit; 0.5 interpreted as half the line width; \caption needs a float |
| H003 | refs.bib | 7-7 | True | close entry chen2022 |

## Needs human confirmation

- {"item": "figure width 0.5\\linewidth assumed for width=0.5", "where": "main.tex:11"}
