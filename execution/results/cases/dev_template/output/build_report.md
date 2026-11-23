# Build report (success)

SUCCESS: main.tex with pdflatex, 2 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 3 edit hunk(s), 3 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: True
- PDF: main.pdf (1 pages)

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G01 | True | \title{...} is set | template:* |
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |
| R1 | True | journal name set via \journalname | changes.json |
| R2 | True | keywords via \keywords{} | changes.json |
| R3 | True | template class jcsa used | changes.json |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | jcsa.cls | 1-14 | True | template class copied unchanged from template/ (v1.2) next to main.tex |
| H002 | main.tex | 3-4 | True | required by template (task.md); keywords given in task.md |
| H003 | main.tex | 17-17 | True | exact file name (Linux is case-sensitive) |
