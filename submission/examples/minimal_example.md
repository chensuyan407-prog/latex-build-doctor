# Minimal invocation example (illustrative - not a platform case)

Input `/input/case.json`:
```json
{"case_id": "demo_math", "task": "Fix the math in model.tex so that it compiles; keep numbering, labels, symbols and values.",
 "output_contract": {"fields": ["fixed_tex", "compile_log", "edits", "open_questions"]}}
```
`/input/model.tex` (excerpt, line numbers left):
```latex
 6 \begin{equation}
 7   L(\theta) &= \sum_{i=1}^{N} \ell(f_\theta(x_i), y_i) \label{eq:loss}
 8 \end{equation}
10 \begin{equation}
11   R(\theta) = \lambda \left( \|\theta\|_2^2 \label{eq:reg}
12 \end{equation}
13 where $\theta \in \mathbb{R}^d$ and the prediction is
14 \[
15   \hat{y} = W x + b
16
17 \]
```

Calls:
```bash
python $SKILL_DIR/scripts/lx_init.py --case /input/case.json --out /app/output --work /app/work
python $SKILL_DIR/scripts/lx_build.py --work /app/work --out /app/output
```

Console output of the build (example, shortened; 9 raw TeX errors -> 4 root causes):
```
status: partial
ROOT CAUSES (fix top-down; follow-on errors hidden):
  E004 undefined_cs  model.tex:13  Undefined control sequence.
       src: where $\theta \in \mathbb{R}^d$ and the prediction is
       fix: \mathbb is provided by package amssymb, which is not loaded: add \usepackage{amssymb} ...
  E001 alignment     model.tex:7   Misplaced alignment tab character &.
  E003 brace         model.tex:12  Missing \right. inserted.        (+1 follow-on)
  S001 math_mode     model.tex:16  blank line inside display math opened at line 14  (+2 follow-on)
  warn unit_italic   model.tex:18  unit set in math italic: $3 s$
```

The agent edits `/app/work/src/model.tex`, writes `/app/work/changes.json`:
```json
{"changes": [
  {"file": "model.tex", "line": 3, "from": "", "to": "\\usepackage{amssymb}", "reason": "\\mathbb undefined", "fixes": "E004", "type": "package"},
  {"file": "model.tex", "line": 8, "from": "L(\\theta) &= ", "to": "L(\\theta) = ", "reason": "& not allowed in equation", "fixes": "E001", "type": "math"},
  {"file": "model.tex", "line": 12, "from": "\\|_2^2 \\label", "to": "\\|_2^2 \\right) \\label", "reason": "\\left( had no \\right", "fixes": "E003", "type": "math"},
  {"file": "model.tex", "line": 17, "from": "\n\n\\]", "to": "\n\\]", "reason": "blank line in display math", "fixes": "S001", "type": "math"}],
 "needs_confirmation": [{"item": "scope of the parenthesis closed after \\|\\theta\\|_2^2", "where": "model.tex:12"}]}
```
and rebuilds: `status: success`, 2 pdflatex passes, `reproducible (2 clean builds, SOURCE_DATE_EPOCH=1704067200): byte-identical PDF`.

`/app/output/result.json` (example, shortened):
```json
{"case_id": "demo_math", "status": "success",
 "fixed_tex": {"source_dir": "src/", "main_tex": "src/model.tex", "pdf": "model.pdf", "...": "..."},
 "compile_log": "build_logs/",
 "edits": [{"hunk": "H001", "file": "model.tex", "new_lines": [3, 3], "reasons": ["\\mathbb undefined"], "documented": true}, "..."],
 "open_questions": [{"item": "scope of the parenthesis closed after \\|\\theta\\|_2^2", "where": "model.tex:12"}],
 "build": {"engine": "pdflatex", "commands": ["pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape model.tex", "..."],
           "converged": true, "reproducibility": {"byte_identical": true}},
 "uncertainty": [], "environment": {"distribution": "TeX Live 2026", "...": "..."}}
```
