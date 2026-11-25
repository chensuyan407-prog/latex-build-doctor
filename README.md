# latex-build-doctor 0.2.0 — submission bundle for 写作13｜LaTeX 写作与编译

Skill for the LaTeX **compile → diagnose → fix → verify** loop. Scripts pre-check a project (classes, packages, .bst,
.bib, graphics with exact letter case, fonts, tools), build it with the right engine and number of passes, and turn the
TeX/BibTeX/biber logs into **root causes** with file:line, the source line, an error class and a concrete fix; follow-on
errors are grouped under their cause. Every edit is diffed against the original and must have a change record; changed
numbers/keys and numbers not found in the input materials are flagged. A second clean build with a fixed
`SOURCE_DATE_EPOCH` checks that the PDF is byte-identical. Outputs: editable `src/`, PDF, previews, `result.json`,
`build_report.md`, `BUILD.md`/`build.sh`/`latexmkrc` with package versions.

| path | content |
|---|---|
| `submission/` | **the Skill**: `SKILL.md`, `scripts/` (lx_init, lx_build, lx_log, lx_static, lx_table, lx_common), `rules/`, `examples/`, `README.md` (method, results, limits) |
| `skills/SKILL.md` | copy of the Skill entry file |
| `src/reproduce.py` | reruns the whole self-evaluation (≈3-4 min, needs TeX Live) |
| `tests/` | 9 author-written broken projects (`cases/*/input`), gold roots + gold fixes + mutation probes (`eval/gold`), `run_eval.py`, `run_robust.py`, `FREEZE.sha256` |
| `execution/` | `run.log`, `results/metrics.json`, `metrics_holdout_at_freeze.json`, `robustness.json`, `eval_rows*.json`, `commands*.json`, per-case outputs (`results/cases/*/output`) |
| `arm_manifest.json`, `characterization.json`, `trace/trace.jsonl` | ARM bundle metadata |

## Reproduce

```bash
python src/reproduce.py
```

## Results (author-written cases; not the platform's fixed cases; no model was run)

| set | gold root causes | found | precision | baseline: first error | baseline: all log errors | fix → expected status | byte-identical rebuild |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev (6 cases, rules written on them) | 22 | 22 | 22/22 | 3 | 12 | 6/6 | 6/6 |
| held-out at freeze (3 cases) | 11 | 10 | 11/13 | 3 | 6 | 3/3 | 3/3 |
| held-out after post-freeze fixes | 11 | 10 | 11/11 | 3 | 6 | 3/3 | 3/3 |

Mutation probes (unrecorded edit, silent value change, number not in materials, requirement removed): 6/6.
Robustness 11/11. Details, the held-out miss and the post-freeze fixes: `submission/README.md`.
