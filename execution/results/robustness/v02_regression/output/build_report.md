# Build report (partial)

PARTIAL: main.tex with pdflatex, 3 engine pass(es) + bibtex; 2 error(s) in log (2 root cause(s) overall), 0 undefined ref(s), 1 undefined citation(s), 0 overfull box(es) >1pt; 0 edit hunk(s), 0 documented.

- commands: `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `bibtex main` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex` -> `pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape main.tex`
- converged: True; reproducible: not checked
- PDF: main.pdf (1 pages)

## Root causes (fix in this order)

| id | class | where | message | hint |
|---|---|---|---|---|
| E002 | undefined_cs | main.tex:6 | Undefined control sequence. <argument> \string \@writefile {\csname ext@\@captype \endcsname }{\protect \contentsline {\@captype }{\protect \numberline {\csname (+1 follow-on) | Undefined command \SI: \SI is provided by package siunitx, which is not loaded: add \usepackage{siunitx} to the preamble (check the template allows it). |
| S001 | undefined_cite | main.tex:4 | \cite{missing2021}: no entry with this key in the bibliography | The reference is missing from the .bib: add it only from the source material, else mark for human confirmation. |

## Warnings

| id | class | where | message |
|---|---|---|---|
| W001 | undefined_cite | main.tex:4 | Package natbib Warning: Citation `missing2021' on page 1 undefined on input line 4. |
| N001 | undefined_cite | None:None | Warning--I didn't find a database entry for "missing2021" |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Uncertainty / limits

- byte-reproducibility not tested (build failed, errors remain or --no-repro)
