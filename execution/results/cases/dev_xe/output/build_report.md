# Build report (success)

SUCCESS: main.tex with xelatex, 2 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 3 edit hunk(s), 3 documented.

- commands: `xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex` -> `xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex`
- converged: True; reproducible: True
- PDF: main.pdf (1 pages)

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G01 | True | \title{...} is set | template:* |
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | main.tex | 1-1 | True | ctexart + fontspec need XeLaTeX |
| H002 | main.tex | 4-4 | True | font required by the task; NoSuchSerif Pro not installed |
| H003 | main.tex | 16-16 | True | unit upright; value unchanged |
