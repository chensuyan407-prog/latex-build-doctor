# Build report (success)

SUCCESS: model.tex with pdflatex, 2 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 5 edit hunk(s), 5 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape model.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape model.tex`
- converged: True; reproducible: True
- PDF: model.pdf (1 pages)

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | model.tex | 3-3 | True | \mathbb undefined |
| H002 | model.tex | 8-8 | True | '&' is not allowed in a single-line equation |
| H003 | model.tex | 12-12 | True | \left( had no \right; closed after the norm (needs confirmation) |
| H004 | model.tex | 17-16 | True | blank line inside display math; unit upright, value unchanged |
| H005 | model.tex | 18-18 | True | blank line inside display math; unit upright, value unchanged |

## Needs human confirmation

- {"item": "closing parenthesis of \\left( placed after \\\|\\theta\\\|_2^2 - author to confirm the intended scope", "where": "model.tex:12"}
