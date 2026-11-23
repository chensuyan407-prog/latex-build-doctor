#!/usr/bin/env python3
"""Reproduce the self-evaluation of the latex-build-doctor Skill.

Run from the bundle root:   python src/reproduce.py      (needs Python 3.8+ and TeX Live with pdflatex, xelatex, bibtex, biber)

1. tests/run_eval.py --set all: 9 author-written broken LaTeX projects (6 dev, 3 held-out written after the code freeze):
   root-cause recall/precision vs gold, baselines from the same compiler log, gold fix -> rebuild -> status, audit,
   byte-identical second build, mutation probes -> execution/results/{metrics,eval_rows,commands}.json + cases/;
2. tests/run_robust.py: 11 robustness checks -> execution/results/robustness.json;
3. keeps the held-out result recorded at the freeze (execution/results/metrics_holdout_at_freeze.json);
4. writes execution/run.log, trace/trace.jsonl, characterization.json, arm_manifest.json.
No language model is called; the platform's fixed cases are not part of this.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "execution", "results")
TRACE = []


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def step(kind, **kw):
    TRACE.append(dict(step_type=kind, timestamp=now(), step_order=len(TRACE) + 1, **kw))


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def run(args, cid):
    step("tool_call", tool_name="python", tool_call_id=cid, tool_args={"argv": args})
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    step("tool_result", tool_call_id=cid, exit_code=r.returncode, stdout_tail=r.stdout[-600:])
    return r


def main():
    t0 = time.time()
    os.makedirs(os.path.join(ROOT, "trace"), exist_ok=True)
    step("thought", title="Plan", body="Compile the 9 broken projects with the Skill, compare root causes with gold, apply gold fixes with change records, "
                                       "rebuild and verify status, audit and byte-reproducibility; run robustness checks; record metrics, manifest and trace.")
    freeze = []
    with open(os.path.join(ROOT, "tests", "FREEZE.sha256"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                h, f = line.split(None, 1)
                f = f.strip().lstrip("*").lstrip("./")
                freeze.append("%s: %s" % (f, "unchanged since freeze" if sha(os.path.join(ROOT, "submission", f)) == h else "CHANGED after freeze (post-freeze fix)"))
    r1 = run(["tests/run_eval.py", "--set", "all"], "c1")
    r2 = run(["tests/run_robust.py"], "c2")
    with open(os.path.join(ROOT, "execution", "run.log"), "w", encoding="utf-8") as log:
        log.write("# reproduce.py run at %s\n$ python tests/run_eval.py --set all\n%s\n%s\n[exit %d]\n\n" % (now(), r1.stdout, r1.stderr, r1.returncode))
        log.write("$ python tests/run_robust.py\n%s\n%s\n[exit %d]\n\n" % (r2.stdout, r2.stderr, r2.returncode))
        log.write("# frozen files vs tests/FREEZE.sha256 (frozen before the held-out cases were written)\n" + "\n".join(freeze) + "\n")
        log.write("# post-freeze fixes: XeTeX/DVI engines get -output-comment so the PDF Creator has no build-minute timestamp (lx_build.py; found when a rerun of dev_xe gave a different PDF); commands/ends inside an undefined environment grouped under it (lx_log.py); cite/ref/label key comparison "
                  "across command variants and digit-adjacent number tokens (lx_build.py); env_mismatch hint text (lx_log.py); README counts\n")
        log.write("# per-call argv/exit/seconds/stdout tails: execution/results/commands.json and commands_robustness.json\n")
    if r1.returncode != 0 or r2.returncode != 0:
        print(r1.stdout[-3000:], r1.stderr[-2000:], r2.stdout[-2000:])
        sys.exit(1)
    m = load(os.path.join(RES, "metrics.json"))
    dev, ho = m["sets"]["dev"], m["sets"]["holdout"]
    hf = load(os.path.join(RES, "metrics_holdout_at_freeze.json"))["sets"]["holdout"]
    rob = load(os.path.join(RES, "robustness.json"))
    m["holdout_at_freeze"] = hf
    m["robustness"] = {c["check"]: c["passed"] for c in rob["checks"]}
    with open(os.path.join(RES, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    step("observation", title="Result", body=json.dumps({"dev_recall": dev["root_recall"], "holdout_recall_at_freeze": hf["root_recall"],
                                                         "holdout_precision_at_freeze": hf["root_precision"], "holdout_precision_after_fix": ho["root_precision"],
                                                         "robustness": "%d/%d" % (rob["passed"], rob["total"])}))
    wall = round(time.time() - t0, 2)

    def frac(s):
        a, b = s.split("/")
        return int(a) / int(b) if int(b) else 0.0

    rows = [
        ("root causes found, dev (6 cases, rules written on them)", dev["root_recall"], 1.0, 0.1,
         "%d gold roots; baselines on the same log: first error %.3f, all log errors %.3f (location only, one-to-one)" % (dev["gold_roots"], dev["baseline_first_error_recall"], dev["baseline_all_log_errors_recall"])),
        ("root-cause precision, dev", dev["root_precision"], 1.0, 0.1, "%d reported roots from %d raw compiler errors" % (dev["reported_roots"], dev["raw_log_errors"])),
        ("root causes found, held-out at code freeze", hf["root_recall"], 1.0, 0.3, "%d gold roots in 3 cases written after the freeze; missed: %s" % (hf["gold_roots"], "; ".join(hf["missed"]))),
        ("root-cause precision, held-out at code freeze", hf["root_precision"], 1.0, 0.3, "%d reported roots" % hf["reported_roots"]),
        ("root-cause precision, held-out after post-freeze fixes", ho["root_precision"], 1.0, 0.1, "no longer a clean held-out measure"),
        ("baseline first-error recall, held-out", ho["baseline_first_error_recall"], 1.0, 1.0, "for comparison: what an agent sees when it stops at the first message"),
        ("gold fix -> expected status (all cases)", (frac(dev["fix_status_ok"]) * 6 + frac(ho["fix_status_ok"]) * 3) / 9, 1.0, 0.0, "dev %s, held-out %s" % (dev["fix_status_ok"], ho["fix_status_ok"])),
        ("byte-identical second clean build (all cases)", (frac(dev["byte_identical_rebuilds"]) * 6 + frac(ho["byte_identical_rebuilds"]) * 3) / 9, 1.0, 0.0, "SOURCE_DATE_EPOCH fixed; PDF SHA-256 compared"),
        ("audit clean after documented gold fix, held-out at freeze", frac(hf["audit_clean_after_documented_fix"]), 1.0, 0.5, "false flags at freeze fixed after it (after fix %s)" % ho["audit_clean_after_documented_fix"]),
        ("mutation probes caught (unrecorded edit, silent number change, number not in materials, requirement removed)", frac(dev["mutation_probes_caught"]), 1.0, 0.0, dev["mutation_probes_caught"]),
        ("robustness checks passed", rob["passed"] / rob["total"], 1.0, 0.0, ", ".join(c["check"] for c in rob["checks"])),
    ]
    char = {"deviations_from_paper": [{"target": t, "metric": "absolute_error", "actual_value": round(a, 4), "reference_value": ref,
                                       "score": round(max(0.0, 1 - abs(a - ref) / tol), 4) if tol else (1.0 if abs(a - ref) < 1e-9 else 0.0),
                                       "explanation": ex, "evidence_artifact": "metrics", "tolerance": tol} for t, a, ref, tol, ex in rows],
            "notes": "Self-evaluation on author-written LaTeX projects with planted faults and author gold; the platform's three fixed cases and any model run "
                     "are not part of it. Scores use max(0, 1 - deviation/tolerance) against the ideal value 1.0. The baseline row is a reference, not a target."}
    with open(os.path.join(ROOT, "characterization.json"), "w", encoding="utf-8") as fh:
        json.dump(char, fh, ensure_ascii=False, indent=1)
    arts = [("metrics", "execution/results/metrics.json", "metric", "json"), ("eval_rows", "execution/results/eval_rows.json", "data", "json"),
            ("metrics_holdout_at_freeze", "execution/results/metrics_holdout_at_freeze.json", "metric", "json"),
            ("eval_rows_holdout_at_freeze", "execution/results/eval_rows_holdout_at_freeze.json", "data", "json"),
            ("robustness", "execution/results/robustness.json", "metric", "json"), ("commands", "execution/results/commands.json", "log", "json")]
    for c in ("dev_bib", "dev_env", "dev_math", "dev_multi", "dev_template", "dev_xe", "ho_ieee", "ho_report", "ho_thesis"):
        o = "execution/results/cases/%s/output" % c
        arts += [(c + "_result", o + "/result.json", "data", "json"), (c + "_report", o + "/build_report.md", "data", "markdown"),
                 (c + "_diff", o + "/changes.diff", "data", "diff")]
        pv = os.path.join(ROOT, o, "preview", "page-1.png")
        if os.path.isfile(pv):
            arts.append((c + "_preview", o + "/preview/page-1.png", "figure", "png"))
    manifest = {
        "arm_version": "1.1",
        "paper": {"title": "写作13｜LaTeX 写作与编译 — latex-build-doctor Skill", "challenge_id": "product-arena-07-865de7e4"},
        "entrypoint": "src/reproduce.py",
        "environment": {"dependencies": "requirements.txt", "python_version": ">=3.8", "gpu_required": False,
                        "extra_packages": ["TeX Live (tested 2026: pdfTeX 1.40.29, XeTeX 0.999998, biber, bibtex, kpsewhich, fc-list, pdftoppm, pdffonts)"]},
        "execution": {"log_path": "execution/run.log", "exit_code": 0, "ran_at": now(), "wall_time_s": wall, "ran_by": "agent",
                      "artifacts": [{"id": i, "path": p, "type": t, "format": f, "checksum_sha256": sha(os.path.join(ROOT, p))} for i, p, t, f in arts if os.path.isfile(os.path.join(ROOT, p))]},
        "expected_outputs": [{"name": r_[0], "type": "metric", "produced_by": ["metrics"], "comparison_method": "numeric_tolerance"} for r_ in rows],
        "handoff": {"status": "partial",
                    "next_suggestion": "Run the platform's three fixed cases with the DeepSeek harness (base vs Skill); add template rules and error patterns from those runs; test on MiKTeX and Linux TeX Live.",
                    "hypothesis": "An agent fixes LaTeX projects faster and more correctly when the compiler log is turned into located, explained root causes with follow-on errors grouped, "
                                  "pre-checked dependencies, and an edit audit plus reproducible-build check, instead of reading the first error message."},
    }
    with open(os.path.join(ROOT, "arm_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "trace", "trace.jsonl"), "w", encoding="utf-8") as fh:
        for t in TRACE:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(json.dumps({"wall_s": wall, "rows": [(t, round(a, 3)) for t, a, *_ in rows]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
