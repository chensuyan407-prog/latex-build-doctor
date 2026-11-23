# latex-build-doctor 0.1.0 — reference

Skill for the LaTeX compile → diagnose → fix → verify loop. Entry: `SKILL.md`. Python 3.8+ standard library only;
needs a TeX distribution (tested: TeX Live 2026 on Windows 11 — pdfTeX 1.40.29, XeTeX 0.999998, biber, BibTeX).

## Files

| file | role |
|---|---|
| `scripts/lx_init.py` | copy input → `work/src` + `work/orig`, unpack archives (path-traversal safe), main/engine/bib-tool detection, precheck (kpsewhich, fc-list, file resolution incl. letter case and files only in subfolders) |
| `scripts/lx_build.py` | clean build in `work/build` (engine passes, bibtex/biber, makeindex, until no rerun request), log/blg parsing, static checks, root-cause grouping, diff + change audit, fact guard, requirements, second clean build for byte-reproducibility, all outputs |
| `scripts/lx_log.py` | TeX log parser (file stack, `-file-line-error`, warnings with continuation lines), ≈60 error patterns → classes + hints, cascade grouping; BibTeX/biber .blg parsers |
| `scripts/lx_static.py` | brace/environment/display-math balance with opening line, labels/refs, cite keys vs .bib (case, near misses), .bib syntax (missing comma, unclosed entry, duplicate keys, required fields), tabular column count, label-before-caption, `\resizebox` tables, units/subscripts in italic, package conflicts/order/engine |
| `scripts/lx_table.py` | CSV/TSV/Markdown table → booktabs LaTeX, values verbatim, source map comments |
| `scripts/lx_common.py` | encoding detection, comment/verbatim stripping, argument parsing, tool calls |
| `rules/packages.json` | command → package (260), environment → package (88), conflicts, load-order and engine rules |
| `rules/templates.json` | required items for elsarticle, IEEEtran, llncs, acmart, revtex4-1/4-2, article, generic |

## Method

1. **Precheck before compiling**: every `\documentclass`, `\usepackage`, `\bibliographystyle` is resolved in the main directory
   or via `kpsewhich`; `.bib`, `\input`/`\include`, graphics (with `\graphicspath`) on disk with exact letter case; fonts named
   in fontspec/xeCJK commands via `fc-list`. A class that exists only in `template/` is reported as such (TeX will not find it).
2. **Build** in a fresh copy (`work/build`), `-interaction=nonstopmode -file-line-error -recorder`, `max_print_line=10000`
   (unwrapped log lines), `SOURCE_DATE_EPOCH` fixed. Passes are repeated only while the log asks for a rerun or the `.aux`
   hash changes (max 5). Timeouts per call and per build.
3. **Diagnose**: errors from the final pass + bib log + precheck + static checks are merged, deduplicated and grouped. A
   follow-on error gets `cascade_of` = its root: same command or same missing package again; errors at the same line;
   everything after a runaway/unclosed group in that file; commands inside an undefined environment; repeated identical
   errors (each table row); compiler "not found" duplicates of a precheck finding; static column count under the TeX
   alignment error. Errors raised inside a `.sty`/`.cls` are attributed to the line that loads it. "File ended while
   scanning" is linked to the line where the brace was opened (static scan).
4. **Audit**: `work/orig` vs `work/src` diff hunks ↔ change records; numbers, cite/ref/label keys changed in an edit;
   numbers in edited text found in no input material.
5. **Verify**: status rule (see SKILL.md), second clean build → PDF SHA-256 comparison.

## Self-evaluation (author-written cases; not the platform's cases; no language model involved)

`python ../src/reproduce.py` from the bundle root. 9 projects with planted faults, gold root causes (class + file + line),
gold fixes with change records, mutation probes. Dev set (6 cases) was used while writing the rules; the held-out set (3
cases) was written after the code freeze (`tests/FREEZE.sha256`).

| set | gold roots | recall | precision | baseline: first error | baseline: all log errors | fix → expected status | byte-identical rebuild | audit clean | probes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | 22 | 22/22 | 22/22 | 3/22 | 12/22 | 6/6 | 6/6 | 6/6 | 6/6 |
| held-out at freeze | 11 | 10/11 | 11/13 | 3/11 | 6/11 | 3/3 | 3/3 | 1/3 | – |
| held-out after post-freeze fixes | 11 | 10/11 | 11/11 | 3/11 | 6/11 | 3/3 | 3/3 | 3/3 | – |

Baselines read the same final-pass log: "first error" = what an agent sees if it stops at the first message; "all log
errors" = every `file:line:` error TeX prints (location matched one-to-one, class ignored — generous to the baseline). The
held-out miss: `subfigure` + `subcaption` does not raise an error in TeX Live 2026; the tool reports it as a warning, the gold
expected an error-level root. Post-freeze fixes (listed in `execution/run.log`): commands inside an undefined environment
grouped under it; XeTeX/DVI engines now run with `-output-comment` because XeTeX stamps the build minute into the
PDF `/Creator` (a rerun of `dev_xe` a minute later gave a different PDF; the in-run double build missed it because both builds
fell in the same minute); cite/ref key comparison across command variants (`\citep`→`\cite`); digit-adjacent numbers (`ch3`→`ch03`);
a hint with doubled braces. The gold of `ho_thesis` was written after a first look at the frozen tool's output on it.
Robustness: 11/11 (no main, two mains, infinite loop → timeout, no TeX on PATH, zip input with path traversal entry,
broken changes.json, missing glyphs, missing package, GB18030 input, deterministic re-run, `\today` document reproducible).

## Limits

- Log parsing is heuristic; macro-generated structure (custom table macros, `\def`-built environments) confuses static counts.
- Only TeX Live tested; MiKTeX on-the-fly installation and latexmk custom dependencies are not handled.
- Template rules cover a few classes; other templates need task-specific `requirements`.
- The fact guard compares numbers textually (1,248 = 1248; 0.50 ≠ 0.5 is treated as equal via float canonicalisation).
- Byte-identical output only within the same TeX installation; `\today` follows the clock, not SOURCE_DATE_EPOCH.
- No evaluation with the platform's DeepSeek harness was possible here; the numbers above measure the scripts, not an agent.

Maintainer: chensuyan407-prog · License MIT.
