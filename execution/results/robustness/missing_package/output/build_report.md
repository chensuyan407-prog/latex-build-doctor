# Build report (failed)

FAILED: main.tex with pdflatex, 1 engine pass(es); 1 error(s) in log (1 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 0 edit hunk(s), 0 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: not checked
- PDF: None (None pages)

## Root causes (fix in this order)

| id | class | where | message | hint |
|---|---|---|---|---|
| S001 | missing_package | main.tex:2 | package nosuchpkgxyz.sty not found (not in the project, not in the TeX installation) (+1 follow-on) | Package not installed: install it (tlmgr install), ship the .sty with the project, or remove it if unused (check which commands need it). |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Uncertainty / limits

- TeX stopped at a fatal error: errors after that point are not known yet - fix the root causes and rebuild
- byte-reproducibility not tested (build failed, errors remain or --no-repro)
