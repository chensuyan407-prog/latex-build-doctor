# Build report (success)

SUCCESS: conf.tex with pdflatex, 2 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 3 edit hunk(s), 3 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape conf.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape conf.tex`
- converged: True; reproducible: True
- PDF: conf.pdf (1 pages)

## Warnings

| id | class | where | message |
|---|---|---|---|
| N001 | requirement_failed | conf.tex:None | requirement IEEE03 not met: IEEEkeywords environment |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| IEEE01 | True | \maketitle | template:IEEEtran |
| IEEE02 | True | abstract environment | template:IEEEtran |
| IEEE03 | False | IEEEkeywords environment | template:IEEEtran |
| IEEE04 | True | authors via \IEEEauthorblockN (conference) or \author | template:IEEEtran |
| G01 | True | \title{...} is set | template:* |
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | conf.tex | 3-2 | True | obsolete, conflicts with subcaption; no \subfigure used |
| H002 | conf.tex | 5-5 | True | \STATE / algorithmic environment |
| H003 | conf.tex | 13-13 | True | IEEEtran uses numeric \cite; natbib not used by the template |
