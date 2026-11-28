---
name: latex-build-doctor
description: Compile-diagnose-fix, template-adaptation, and reproducible-build Skill for LaTeX projects (pdfLaTeX, XeLaTeX, LuaLaTeX; BibTeX/biber). Scripts copy the project, discover main file/engine/bib tool, inspect local .cls templates and materials, pre-check classes/packages/.bst/fonts/graphics/\input files (including subfolder classes and Linux case mismatches), run the right passes, turn .log/.blg into ROOT CAUSES with file:line and fix hints (grouping follow-on errors), check static syntax/tables/bib/labels, audit every diff vs original with fact guard, build tables from CSV/TSV/Markdown data, and verify byte-identical rebuilds + previews. Use for fixing LaTeX errors/warnings, migrating manuscripts into templates, writing LaTeX tables/formulas/citations from research materials, CJK/bilingual XeLaTeX builds, and verifying reproducible LaTeX deliverables. Not for non-LaTeX documents or general paper QA without TeX output.
---

# latex-build-doctor (v0.2.0)

You decide author intent; the scripts compile, locate, explain, record and verify. Python 3.8+ standard library only; needs TeX Live / MiKTeX (`pdflatex`/`xelatex`/`lualatex`, `bibtex`/`biber`, `kpsewhich`; optional `chktex`, `fc-list`, `pdftoppm`, `pdftotext`, `pdffonts`, `pdfinfo`).

Run these probes from the skill directory, or set `SKILL_DIR` to the absolute installed skill path.
```bash
command -v python3 && python3 --version
SKILL_DIR="$(pwd -P)"
test -f "$SKILL_DIR/scripts/lx_init.py"
ls -l /input/case.json
command -v pdfinfo pdftoppm pdftotext
```
On Windows, use the Python 3 interpreter on PATH and pass absolute paths. Adjust /input, /app/work and /app/output to match the case.

## Workflow

1. **Init** - copy `/input` (archives unpacked) to `/app/work/src` (edit here) and `/app/work/orig` (never edit):
   ```bash
   python3 "$SKILL_DIR/scripts/lx_init.py" --case /input/case.json --out /app/output --work /app/work
   ```
   Prints `case_id`, `output_contract` fields, main file, engine (+ reason), bib tool, reached files, non-TeX materials, local `.cls` template summary (options/macros/checks), fonts and **PRECHECK problems** (missing files, subfolder classes, Linux case mismatches). Choose an explicit entry with `--main FILE`, `--engine xelatex`, `--src DIR`.
   Confirm the selected main before editing. An explicit CLI entry takes priority over case metadata such as main_tex or primary.
   Without a declaration, init checks for a full document and excludes included or auxiliary candidates.
   An invalid or ambiguous explicit entry stops the command. Use the full project-relative path to resolve ambiguity.
2. **Read** `/input/task.md` and `/input/case.json` completely (template, journal, engine, required items, `output_contract`, what may change). Put verifiable template/task regex checks into `work/changes.json` → `requirements`.
   - **If writing from scratch or migrating into a template**: copy any subfolder `.cls/.sty/.bst` next to your main `.tex` (unchanged), create/update `/app/work/src/main.tex` (with `--main main.tex` if a sample exists in `template/`), convert data tables via `lx_table.py`, and fill required template fields ONLY from `/input` materials (leave visible placeholders + `needs_confirmation` for missing metadata like ORCID/funding).
3. **Build + diagnose**:
   ```bash
   python3 "$SKILL_DIR/scripts/lx_build.py" --work /app/work --out /app/output
   ```
   Prints status, rounds run (`pdflatex pass 1 -> bibtex -> pass 2 -> pass 3`), **ROOT CAUSES** in fix order (`id class file:line message`, `src:`, `log:`, `fix:`, `(+n follow-on)`), warnings, failed requirements, fact-guard hits, and any unmapped `output_contract` fields. Full list: `/app/output/diagnostics.json`. Exit `0` = success, `1` = PDF with remaining issues, `2` = no PDF.
4. **Try conservative automatic repairs, then review remaining root causes**:
   ```bash
   python3 "$SKILL_DIR/scripts/lx_build.py" --work /app/work --out /app/output --auto-fix
   ```
   ChkTeX supplements the built-in static checks when available. Automatic repair uses compiler locations and clear source patterns to escape literal punctuation, close simple groups and environments, add known packages, and resolve unique local graphics. It can restore missing separators marked by spacing, extend consistent row shapes, and wrap supported overwide tables at the local linewidth.

   Repairs are compiled in a staged copy for up to five rounds. Accepted source appears in `output/src/` with `changes.diff` and change records. Build details include the candidate diff and compiler summaries where the case contract permits them. Review ambiguous separators, comments and custom macros manually. To continue editing, copy the reviewed files to `work/src/` and record the edits.

   For manual changes:
   Edit `/app/work/src`, then record diffs cleanly into `work/changes.json` using `lx_record.py` (avoids manual line-number/JSON-escaping errors):
   ```bash
   python3 "$SKILL_DIR/scripts/lx_record.py" --work /app/work --auto --reason "..." --fixes "E001" --type math
   ```
   (Use `--accept-numbers` / `--accept-keys` only when changing a number/key is the intended fix from materials; use `--confirm "..." --where "file:line"` for human-confirmation items; use `--set-field "key=value"` for custom `output_contract` fields.)
   Rebuild (step 3). Repeat until exit `0` or only items requiring human confirmation remain.
5. **Verify the finished deliverables**:
   Run the checklist on the final build. Use --preview-page N for each critical page beyond the first eight.
   Use typed JSON values with --set-field for task-specific contract fields, then rebuild.
   Add unresolved items to needs_confirmation with the source location and the decision needed.

## 编译与内容保真 Checklist

- [ ] The selected entry, engine and template match case.json and the user task.
- [ ] Every source-table column and row survives. Compare cells, units, headers and spans against the source.
- [ ] Width matches the float: use tabularx with flexible text columns and linewidth, or table* for a two-column float.
- [ ] Figures use the supplied assets. Equations, numbering, labels, citation keys and reference targets survive the diff.
- [ ] The final PDF opens, the first page and each key PNG are readable, and no table cells or figures are clipped.
- [ ] Check overfull boxes, unresolved citations/references and missing glyphs in the final log and visual output.
- [ ] result.json has the original case_id, top-level status, and each requested field at the top level and in output_contract. Artifact paths are relative to the output directory. For example, a fixed_source typed as path points to src/main.tex, and preview_paths lists the rendered PNG files.

## changes.json (`/app/work/changes.json`, created by init)

```json
{"changes": [
  {"file": "main.tex", "line": 4, "from": "", "to": "\\usepackage{siunitx}", "reason": "\\SI undefined", "fixes": "E002", "type": "package"},
  {"file": "sections/intro.tex", "line": 3, "from": "\\cite{smith2021}", "to": "\\cite{Smith2021}", "reason": "bib key is Smith2021", "fixes": "S005", "type": "citation", "accept_keys": true},
  {"file": "jcsa.cls", "reason": "template class copied unchanged from template/", "type": "new_file"}],
 "requirements": [{"id": "R1", "desc": "journal name set", "pattern": "\\\\journalname\\{[^}]+\\}"}],
 "needs_confirmation": [{"item": "\\ref{tab:ablation} has no target in materials", "where": "results.tex:26"}],
 "notes": [], "engine": "xelatex", "main": "main.tex", "fields": {"<contract field>": {"value": "..."}}}
```
- `requirements`: regex over comment-free sources reached from main (`absent: true` = must not occur; `severity: "error"` makes status `partial` when unmet). Built-in rules cover `elsarticle`, `IEEEtran`, `llncs`, `acmart`, `revtex4-1/4-2`, `ctexart`/`ctexbook`, `sn-jnl`, `achemso`, `article`, `report`, `book`, `beamer`.

## Fix rules

- **Fix causes, not symptoms.** Never silence errors with `\nonstopmode`, `\let\foo\relax`, `\providecommand` stubs, deleting content, or `\iffalse`.
- **Minimal edits, preserve facts.** Keep wording, numbers, units, citation keys, labels, equation numbering. Fact guard (`number_not_in_materials`) checks edited/new text against all input materials (including `.pdf`/`.csv`/`.md`/`.bib`).
- **Packages**: check template compatibility; keep `hyperref` last (`cleveref` after it); load each package once with all options; remove obsolete/conflicting pairs (`subfigure`+`subcaption`, `algorithmic`+`algpseudocode`, `natbib`+`biblatex`).
- **Engine/fonts**: `fontspec`, `xeCJK`, `unicode-math`, `ctex` → XeLaTeX/LuaLaTeX (`% !TEX program` or `--engine`). Missing font: use template/task font if installed (`fc-list` or TeX `kpsewhich`), else substitute an installed font and record under `needs_confirmation`. Never leave `missing_glyph`.
- **Templates**: never edit `.cls/.sty/.bst`; copy subfolder template files next to main. Fill required items from materials only; mark missing items visibly + `needs_confirmation`.
- **Tables & Math**: match column spec to cells; fit wide tables with `tabularx`/`longtable`/`p{}`/`\small`/`table*` — never `\resizebox`. Generate data tables with `lx_table.py`. Use `align` for `&`, `\[ \]` not `$$`, no blank lines in display math, upright units (`\SI`/`\qty` or `\mathrm{nm}`), `\mathrm{...}` for multi-letter subscripts.
- **References**: `\label` after `\caption`; cite keys are case-sensitive; never invent `.bib` entries/fields; `\addbibresource{x.bib}` requires `.bib`.

## Writing a table from data

```bash
python3 "$SKILL_DIR/scripts/lx_table.py" /input/data.csv --caption "..." --label tab:x [--header "A,B"] [--width natural|tabularx|longtable] [--siunitx] --out /app/work/src/tab_x.tex
```
Then `\input{tab_x}` with `\usepackage{booktabs}` (+ `tabularx`/`longtable`/`siunitx` if chosen). Pass --keep-math for trusted LaTeX math and citation/reference commands in cells. Extra cells cause an error with source line numbers. Values are copied verbatim with `% row k <- file line n` source-map comments.

## Outputs (`/app/output`, rewritten by every build)

`result.json` (case_id, all `output_contract` fields, status `success|partial|failed`, summary, artifacts, build, diagnostics_summary, requirements, changes, change_records, sources {materials, fact_guard}, needs_confirmation, uncertainty, environment) · `src/` · `<main>.pdf` · `preview/page-*.png` · `build_report.md` · `diagnostics.json` · `changes.diff` + `change_log.json` · `BUILD.md`, `build.sh`, `latexmkrc` · `environment.json` · `build_logs/`.

**Status** `success` = PDF produced, 0 log/bib errors, 0 undefined refs/cites, 0 Linux case mismatches or pre-caption labels, passes converged, error-level requirements met, 0 missing glyphs, and verified PDF previews. Clean rebuild with `SOURCE_DATE_EPOCH` (default `1704067200`) checks byte-identical PDF (`--no-repro` skips).

## Exceptions & Limits

| situation | script behavior | your action |
|---|---|---|
| missing `.cls/.sty/.bst` | precheck + log root | copy from materials next to main (unchanged), else confirm replacement |
| case mismatch (`Psi.png` vs `psi.png`) | precheck flags on both Windows & Linux | update TeX path to exact disk case |
| missing font | checks `fc-list` + `kpsewhich` | use installed font or substitute + `needs_confirmation` |
| infinite loop / prompt | `--timeout` (180 s), `--budget` (420 s) → `timeout` root | fix macro recursion / missing file |
| `bib_syntax` / `bib_duplicate` | parsed from `.blg` + static scan | fix `.bib` syntax / deduplicate keys |
| unmapped contract fields | printed as `WARN` in `lx_build.py` | set via `lx_record.py --set-field` |

Limits: heuristic log parsing; macro-generated `&`/`\begin`/`{` can confuse static counts; byte-reproducibility requires same TeX installation (`\today` follows clock, not `SOURCE_DATE_EPOCH`).
