---
name: latex-build-doctor
description: Compile-diagnose-fix loop for LaTeX projects (pdfLaTeX, XeLaTeX, LuaLaTeX; BibTeX/biber) that returns an editable, compiling source tree plus a reproducible build record. Scripts copy the project, find the main file, engine and bib tool, pre-check classes/packages/.bst/fonts/graphics/\input files (incl. files only in a subfolder and filename case mismatches that break on Linux), run the right number of passes, and turn the .log/.blg into ROOT CAUSES with file:line, the source line, the class of error and a concrete fix (missing package for an undefined command, unclosed brace traced to where it was opened, column count vs tabular spec, label before caption, cite key case mismatch, broken .bib field syntax, duplicate keys, engine/font mismatch); follow-on errors are grouped under their cause. Every edit is diffed against the original and must have a change record; changed numbers, citation/label keys and numbers not found in the input materials are flagged. Two clean builds with fixed SOURCE_DATE_EPOCH test byte-identical output. Use for LaTeX compile errors and warnings, undefined references/citations, bibliography problems, formula/table/float fixes, moving a manuscript into a journal or thesis template, writing LaTeX tables from data, and making a build reproducible. Not for content questions about a paper or for non-LaTeX documents.
---

# latex-build-doctor (v0.1.0)

You decide what the author meant; the scripts compile, locate, explain, record and verify. Python 3.8+ standard
library; needs a TeX distribution (TeX Live / MiKTeX: the engine, bibtex/biber, kpsewhich; optional fc-list, pdftoppm,
pdffonts, pdfinfo). `SKILL_DIR` = directory of this file (`/skills/weekly-skill`). Paths below use the evaluator layout
(`/input`, `/app/work`, `/app/output`); change them if yours differ.

## Workflow (typically 4-10 model requests; each build 2-20 s)

1. **Init** - copies the input (archives are unpacked) to `work/src` (edit here) and `work/orig` (never edit):
   ```bash
   python $SKILL_DIR/scripts/lx_init.py --case /input/case.json --out /app/output --work /app/work
   ```
   Prints case_id, contract fields, main file, class, engine (+ reason), bib tool, files reached from main, fonts and
   **PRECHECK problems** (missing class/package/.bst/.bib/graphic/font/tool, class only in a subfolder, case mismatch).
   Wrong guess? `--main FILE`, `--engine xelatex`, `--src DIR`. No .tex at all (writing task): create
   `/app/work/src/main.tex` yourself, then build with `--main main.tex`.
2. **Read** `task.md` and `case.json` completely (template, journal, engine, required items, what may change). Put every
   template/task requirement you can test as a regex into `work/changes.json` → `requirements` (see below).
3. **Build + diagnose**:
   ```bash
   python $SKILL_DIR/scripts/lx_build.py --work /app/work --out /app/output
   ```
   Prints status, the rounds run (`pdflatex pass 1 -> bibtex -> pass 2 -> pass 3`), **ROOT CAUSES** in fix order
   (`id class file:line message`, `src:` the source line, `log:` where TeX stopped, `fix:` what to do, `(+n follow-on)`
   = errors that disappear with it), then warnings, failed requirements and fact-guard hits. Full list: `/app/output/diagnostics.json`.
   Exit 0 = success, 1 = PDF but problems remain, 2 = no PDF.
4. **Fix root causes top-down** in `/app/work/src` (minimal edits, see rules) and add one record per edit to
   `work/changes.json`. Rebuild (step 3). Repeat until exit 0 or only items that need a human remain.
   After a fatal error (missing class/package/font, engine), TeX stopped early: rebuild after fixing it - new errors may appear.
5. **Finish**: the last build already wrote everything to `/app/output` (incl. `result.json`). Unresolvable items go to
   `needs_confirmation`, never into invented content. Out of budget: the last build's output is a valid partial result.

## changes.json (`/app/work/changes.json`, created by init)

```json
{"changes": [
  {"file": "main.tex", "line": 4, "from": "", "to": "\\usepackage{siunitx}", "reason": "\\SI undefined", "fixes": "E002", "type": "package"},
  {"file": "sections/intro.tex", "line": 3, "from": "\\cite{smith2021}", "to": "\\cite{Smith2021}", "reason": "bib key is Smith2021 (same work)", "fixes": "S005", "type": "citation", "accept_keys": true},
  {"file": "results.tex", "line": 9, "from": "{lcc}", "to": "{lccc}", "reason": "4 values per row as in data.csv", "fixes": "E008", "type": "table"},
  {"file": "jcsa.cls", "reason": "template class copied unchanged from template/", "type": "new_file"}],
 "requirements": [{"id": "R1", "desc": "journal name set", "pattern": "\\\\journalname\\{[^}]+\\}"},
                  {"id": "R2", "desc": "no \\resizebox around tables", "pattern": "\\\\resizebox", "absent": true, "severity": "warning"}],
 "needs_confirmation": [{"item": "\\ref{tab:ablation} has no target in the materials", "where": "results.tex:26"}],
 "notes": ["..."], "engine": "xelatex", "main": "main.tex", "fields": {"<contract field>": {"value": "..."}}}
```
- `from` = text in the original, `to` = text in the new file (`""` for pure insert/delete), `line` = line in the new file.
  JSON-escape backslashes (`\\cite`). Each diff hunk without a record → `undocumented_change`; a record matching no edit → `stale_record`.
- `accept_numbers: true` / `accept_keys: true` only when changing a number / cite-ref-label key is the fix (say why and from which source).
- `requirements`: regex over the comment-free sources reached from main; `absent: true` = must not occur; `severity` error (default)
  makes the status partial when unmet. Template rules for elsarticle, IEEEtran, llncs, acmart, revtex are built in (`rules/templates.json`).
- `fields`: only if a contract field is not mapped automatically (result.json maps fields by name: pdf, log, diff, change*, diagnos*/error*,
  command*/build*, environment/version, confirm*, uncertain*/limit*, source*/evidence*, requirement*/template*, tex/artifact/output, summary, status).
- `engine` / `main`: persist a choice for later builds (same as `--engine` / `--main`).

## Fix rules

- **Fix causes, not symptoms.** Handle root causes in the printed order; follow-on errors usually vanish. Do not silence errors with
  `\nonstopmode`, `\let\foo\relax`, `\providecommand` stubs, deleting content or `\iffalse`.
- **Minimal edits, author intent.** Keep wording, numbers, units, citation keys, labels, equation numbering. Changing a value, key or
  the scope of a formula (`\left( ... \right)`) needs a reason from the materials; if the materials do not decide it, make the smallest
  compiling fix and list it under `needs_confirmation`.
- **Packages**: add the package the hint names (check the template allows it); keep `hyperref` last (`cleveref` after it); one load per
  package with all options (option clash); remove obsolete/conflicting packages only if nothing else needs them.
- **Engine/fonts**: `fontspec`, `xeCJK`, `unicode-math`, ctex → XeLaTeX/LuaLaTeX (fix the `% !TEX program` line or pass `--engine`).
  Missing font: use the font the template/task names if installed (check `fc-list`), else an installed equivalent and record the
  substitution as needs_confirmation. Never leave missing glyphs (`missing_glyph` = blank characters in the PDF).
- **Templates**: never edit the template `.cls/.sty/.bst`; copy them next to the main file. Fill every required item from the materials
  only; if a required item (e.g. funding, ORCID) is not in the materials, leave a visible placeholder and list it.
- **Tables**: column spec must match the cells; widen with `tabularx`/`p{}` columns, `\small`, `table*` - not `\resizebox`. Write tables
  from data with `lx_table.py` (values verbatim + source map). **Math**: `align` for `&`, `\[ \]` not `$$`, no blank lines in display
  math, upright units (`\SI`/`\qty` or `\mathrm{nm}`) and descriptive subscripts (`x_{\mathrm{max}}`).
- **References**: `\label` after `\caption`; cite keys are case-sensitive; never invent .bib entries or fields - missing data goes to
  `needs_confirmation`. `\addbibresource{x.bib}` needs the extension.
- **Do not fabricate**: the fact guard lists numbers in edited/new text that occur in no input file (`number_not_in_materials`).

## Writing a table from data (optional)

```bash
python $SKILL_DIR/scripts/lx_table.py /input/data.csv --caption "..." --label tab:x [--header "A,B"] [--width tabularx] [--siunitx] --out /app/work/src/tab_x.tex
```
then `\input{tab_x}` and `\usepackage{booktabs}`; the snippet ends with `% row k <- data.csv line n` comments.

## Outputs (`/app/output`, rewritten by every build)

`result.json` (case_id, all contract fields, status `success|partial|failed`, summary, artifacts, build {commands, rounds,
passes, converged, reproducibility}, diagnostics_summary {root_causes, undefined refs/cites, overfull boxes, missing glyphs},
requirements, changes, change_records, sources {materials, fact_guard}, needs_confirmation, uncertainty, environment) ·
`src/` final editable project · `<main>.pdf` · `preview/page-*.png` · `build_report.md` · `diagnostics.json` ·
`changes.diff` + `change_log.json` (every hunk with its reasons) · `BUILD.md`, `build.sh`, `latexmkrc` (exact commands,
SOURCE_DATE_EPOCH, engine/bibtool versions, distribution, every package date+version from the log, project files read, PDF fonts
and whether embedded) · `environment.json` · `build_logs/` (final .log/.blg).

**Status** success = PDF, no errors, no undefined refs/cites, passes converged, all error-level requirements met. Reproducibility:
after a clean build a second clean build runs with the same SOURCE_DATE_EPOCH (default 1704067200) and the PDF SHA-256 is compared
(`--no-repro` skips it, e.g. for very long builds).

## Exceptions

| situation | what the scripts do | what you do |
|---|---|---|
| missing package/class/.bst | precheck + log root (kpsewhich), name, where loaded | install not possible → ship the file if it is in the materials, else replace only with approval; record |
| class/.sty only in a subfolder | precheck `exists at template/x.cls` | copy next to main (record `new_file`) |
| missing font | precheck via fc-list + fontspec error | installed font named by the task/template, else substitute + needs_confirmation |
| engine mismatch | engine from `% !TEX program`, else from packages | correct the magic line / `--engine` |
| no main / several mains | lists candidates | `--main` |
| infinite loop / prompt | per-call `--timeout` (180 s), whole build `--budget` (420 s) → `timeout` root with last file:line | fix the recursion |
| missing tool (biber, engine) | `missing_tool` precheck | choose another engine/backend only if the template allows |
| read-only or locked output | `permission` class; builds run in `work/build` | use a writable `--work/--out` |
| broken changes.json | warning `changes_json_invalid`, records ignored | fix the JSON |
| non-UTF-8 sources | read as UTF-8/GB18030/CP1252, encoding reported | keep the file encoding unless the task says otherwise |
| shell-escape packages (minted, svg) | `shell_escape` root | `--shell-escape` only for trusted sources; record it |

## Limits

Heuristic log parsing (TeX logs are not structured); roots are ranked guesses with evidence, read `src:`/`log:` before editing.
The static checks do not expand macros (user macros that produce `&`, `\begin` or `{` can confuse column/brace counts). Template
rules cover a few common classes; others need `requirements`. Byte-identical PDFs need SOURCE_DATE_EPOCH support (TeX Live 2016+);
`\today` still prints the build day. The two builds run back to back, so a timestamp with minute resolution that ignores
SOURCE_DATE_EPOCH can slip through (XeTeX's is neutralised with `-output-comment`). Not tested on MiKTeX auto-install or on Overleaf-specific features (latexmkrc with custom deps).
