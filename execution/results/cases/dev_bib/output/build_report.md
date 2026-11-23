# Build report (partial)

PARTIAL: paper.tex with pdflatex, 3 engine pass(es) + biber; 0 error(s) in log (1 root cause(s) overall), 0 undefined ref(s), 1 undefined citation(s), 0 overfull box(es) >1pt; 3 edit hunk(s), 3 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex` -> `biber paper` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape paper.tex`
- converged: True; reproducible: True
- PDF: paper.pdf (1 pages)

## Root causes (fix in this order)

| id | class | where | message | hint |
|---|---|---|---|---|
| S001 | undefined_cite | paper.tex:14 | \parencite{wu2021survey}: no entry with this key in the bibliography | The reference is missing from the .bib: add it only from the source material, else mark for human confirmation. |

## Warnings

| id | class | where | message |
|---|---|---|---|
| W002 | undefined_cite | paper.tex:14 | LaTeX Warning: Citation 'wu2021survey' on page 1 undefined on input line 14. |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| ART01 | True | \maketitle after \title | template:article |
| G01 | True | \title{...} is set | template:* |
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Changes (diff vs original input)

| hunk | file | new lines | documented | reason |
|---|---|---|---|---|
| H001 | library.bib | 13-13 | True | missing comma between title and booktitle |
| H002 | library.bib | 25-24 | True | duplicate key scarselli2009; kept the complete first entry (same work: same title, year) |
| H003 | paper.tex | 3-3 | True | \addbibresource needs the file extension |

## Needs human confirmation

- {"item": "\\parencite{wu2021survey}: no entry in library.bib and no bibliographic data in the materials", "where": "paper.tex:14"}
