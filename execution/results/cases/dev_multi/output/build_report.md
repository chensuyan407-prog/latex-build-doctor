# Build report (partial)

PARTIAL: main.tex with pdflatex, 3 engine pass(es) + bibtex; 0 error(s) in log (1 root cause(s) overall), 1 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 5 edit hunk(s), 5 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `bibtex main` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: True
- PDF: main.pdf (2 pages)

## Root causes (fix in this order)

| id | class | where | message | hint |
|---|---|---|---|---|
| S001 | undefined_ref | sections/results.tex:26 | \ref{tab:ablation}: no \label{tab:ablation} in the project | closest existing labels: tab:main - fix the key, do not invent a target. |

## Warnings

| id | class | where | message |
|---|---|---|---|
| W002 | undefined_ref | sections/results.tex:26 | LaTeX Warning: Reference `tab:ablation' on page 1 undefined on input line 26. |
| N004 | bib_field | refs.bib:9 | @inproceedings{lee2019} has no booktitle |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| ART01 | True | \maketitle after \title | template:article |
| G01 | True | \title{...} is set | template:* |
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | main.tex | 4-6 | True | \SI is undefined (siunitx not loaded); \toprule/\midrule/\bottomrule undefined; load hyperref last |
| H002 | main.tex | 8-7 | True | load hyperref last |
| H003 | sections/intro.tex | 3-4 | True | close the \textbf group (bold scope as in the sentence); bib key is Smith2021 (case-sensitive); same work |
| H004 | sections/results.tex | 7-7 | True | label after caption so \ref gives the table number |
| H005 | sections/results.tex | 9-9 | True | label after caption so \ref gives the table number; 4 columns in every row (Method, RMSE, MAE, Time) as in data.csv |

## Needs human confirmation

- {"item": "Table~\\ref{tab:ablation} has no target in the materials (no ablation table)", "where": "sections/results.tex:26"}
- {"item": "lee2019 (@inproceedings) has no booktitle; not in materials", "where": "refs.bib:9"}
