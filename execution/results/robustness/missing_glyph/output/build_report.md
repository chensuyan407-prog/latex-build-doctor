# Build report (partial)

PARTIAL: main.tex with xelatex, 1 engine pass(es); 0 error(s) in log (0 root cause(s) overall), 0 undefined ref(s), 0 undefined citation(s), 0 overfull box(es) >1pt; 0 edit hunk(s), 0 documented.

- commands: `xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex`
- converged: True; reproducible: True
- PDF: main.pdf (1 pages)

## Warnings

| id | class | where | message |
|---|---|---|---|
| W001 | missing_glyph | main.tex:4 | Missing character: There is no 结 (U+7ED3) in font [lmroman10-regular]:mapping=tex-text;! |
| W002 | missing_glyph | main.tex:4 | Missing character: There is no 果 (U+679C) in font [lmroman10-regular]:mapping=tex-text;! |

## Requirements

| id | ok | requirement | origin |
|---|---|---|---|
| G02 | True | no unresolved placeholders (TODO/XXX/??/<insert>) | template:* |

## Uncertainty / limits

- 2 missing glyph(s) in the PDF (characters not in font)
