# Build report (failed)

FAILED: main.tex with pdflatex, 1 engine pass(es); 0 error(s) in log (1 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 0 edit hunk(s), 0 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: not checked
- PDF: None (None pages)

## Root causes (fix in this order)

| id | class | where | message | hint |
|---|---|---|---|---|
| S001 | missing_tool | None:None | pdflatex is not on PATH | Install TeX Live / MiKTeX with pdflatex, or choose another engine (--engine). |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Uncertainty / limits

- byte-reproducibility not tested (build failed, errors remain or --no-repro)
