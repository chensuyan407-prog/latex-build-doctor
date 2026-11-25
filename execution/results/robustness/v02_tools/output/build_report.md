# Build report (success)

SUCCESS: main.tex with pdflatex, 2 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 2 edit hunk(s), 2 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: not checked
- PDF: main.pdf (1 pages)

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | main.tex | 1-5 | True | add data table |
| H002 | tab.tex | 1-22 | True | add data table |

## Uncertainty / limits

- byte-reproducibility not tested (build failed, errors remain or --no-repro)
