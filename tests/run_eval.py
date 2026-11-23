#!/usr/bin/env python3
"""Self-evaluation of latex-build-doctor on author-written LaTeX projects with planted faults.

  python tests/run_eval.py [--set dev|holdout|all] [--cases a,b] [--keep]

Per case: lx_init + lx_build on the broken project -> compare the reported ROOT causes with the gold list
(class family + file + line +-1); baselines computed from the same compiler log: B1 = first error only (what an agent
sees when it stops at the first message), B2 = every error line TeX prints (no grouping, no static checks).
Then the gold fix + change records are applied to work/src, rebuilt, and status / audit / reproducibility are checked.
Mutation probes add an unrecorded edit or a silent number change and expect the audit to flag it.
Writes execution/results/{metrics.json, eval_rows.json, commands.json} and per-case outputs under execution/results/cases/.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "submission", "scripts")
CASES = os.path.join(ROOT, "tests", "cases")
GOLD = os.path.join(ROOT, "tests", "eval", "gold")
RES = os.path.join(ROOT, "execution", "results")
COMMANDS = []
FAMILY = {
    "undefined_cs": {"undefined_cs"}, "undefined_env": {"undefined_env"},
    "brace": {"brace", "runaway", "no_end"}, "runaway": {"brace", "runaway", "no_end"},
    "env_mismatch": {"env_mismatch", "no_end"}, "alignment": {"alignment", "table_columns"}, "table_columns": {"alignment", "table_columns"},
    "math_mode": {"math_mode"}, "undefined_cite": {"undefined_cite"}, "undefined_ref": {"undefined_ref"}, "float_label": {"float_label"},
    "missing_package": {"missing_package"}, "missing_class": {"missing_class"}, "missing_file": {"missing_file"}, "missing_font": {"missing_font"},
    "engine_mismatch": {"engine_mismatch"}, "bib_missing_file": {"bib_missing_file"}, "bib_syntax": {"bib_syntax"}, "bib_duplicate": {"bib_duplicate"},
    "option_clash": {"option_clash", "load_order"}, "already_defined": {"already_defined", "package_conflict"}, "package_conflict": {"already_defined", "package_conflict"},
    "structure": {"structure"}, "duplicate_label": {"duplicate_label"}, "unicode_char": {"unicode_char"}, "capacity": {"capacity", "timeout"}, "timeout": {"timeout", "capacity"},
    "number_unit": {"number_unit"}, "bib_field": {"bib_field"}, "load_order": {"load_order", "option_clash"},
}


def py(args, cwd=ROOT, timeout=900):
    t0 = time.time()
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    COMMANDS.append({"argv": [os.path.relpath(a, ROOT).replace(os.sep, "/") if os.path.isabs(a) and a.startswith(ROOT) else a for a in args],
                     "exit": r.returncode, "seconds": round(time.time() - t0, 2), "stdout_tail": r.stdout[-1500:], "stderr_tail": r.stderr[-800:]})
    return r


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def match(g, d):
    if d.get("class") not in FAMILY.get(g["class"], {g["class"]}):
        return False
    if g.get("file") and d.get("file") != g["file"]:
        return False
    if g.get("line") is None:
        return True
    rows = d.get("rows") or []
    if g.get("lines") and d.get("line") in g["lines"]:
        return True
    return d.get("line") is not None and (abs(d["line"] - g["line"]) <= 1 or g["line"] in rows)


def loc_match(g, d):
    """Baselines: location only (file + line +-1), any class."""
    return d.get("file") == g.get("file") and d.get("line") is not None and g.get("line") is not None and abs(d["line"] - g["line"]) <= 1


def one_to_one(gold, errs):
    """Greedy one-to-one matching: one log message can explain at most one gold cause."""
    used, hits = set(), []
    for gr in gold:
        for k, d in enumerate(errs):
            if k not in used and loc_match(gr, d):
                used.add(k)
                hits.append(gr["id"])
                break
    return hits


def raw_log_errors(log_text, main_dir_rel):
    """Every error TeX prints with -file-line-error ('file:line: msg' or '! msg' + 'l.N'), no grouping."""
    out = []
    lines = log_text.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"^(.*?\.(?:tex|bib|sty|cls)):(\d+): (.*)$", l)
        if m:
            f = re.sub(r"^\./", "", m.group(1).replace("\\", "/"))
            out.append({"file": os.path.normpath(os.path.join(main_dir_rel, f)).replace(os.sep, "/") if main_dir_rel else f, "line": int(m.group(2)), "message": m.group(3)})
        elif l.startswith("! ") and not l.startswith("! Emergency") and not l.startswith("! ==>"):
            ln = None
            for k in range(i + 1, min(i + 30, len(lines))):
                mm = re.match(r"^l\.(\d+) ", lines[k])
                if mm:
                    ln = int(mm.group(1))
                    break
            out.append({"file": None, "line": ln, "message": l[2:]})
    return out


def apply_fix(src, fix):
    for op in fix:
        p = os.path.join(src, op["file"])
        if op.get("create"):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(op["create"])
            continue
        if op.get("move_from"):
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            shutil.copy2(os.path.join(src, op["move_from"]), p)
            continue
        with open(p, encoding=op.get("encoding", "utf-8"), newline="") as fh:
            t = fh.read()
        if op["find"] not in t:
            raise RuntimeError("gold fix: text not found in %s: %r" % (op["file"], op["find"][:80]))
        t = t.replace(op["find"], op["replace"], 1 if not op.get("all") else -1)
        with open(p, "w", encoding=op.get("encoding", "utf-8"), newline="") as fh:
            fh.write(t)


def run_case(cid, keep, outbase):
    g = load(os.path.join(GOLD, cid + ".json"))
    inp = os.path.join(CASES, cid, "input")
    base = os.path.join(outbase, cid)
    work, out = os.path.join(base, "work"), os.path.join(base, "output")
    shutil.rmtree(base, ignore_errors=True)
    extra = g.get("build_args", [])
    r0 = py([os.path.join(S, "lx_init.py"), "--case", os.path.join(inp, "case.json"), "--out", out, "--work", work] + g.get("init_args", []))
    t0 = time.time()
    r1 = py([os.path.join(S, "lx_build.py"), "--work", work, "--out", out, "--quiet", "--no-repro"] + extra)
    t_build = time.time() - t0
    res = load(os.path.join(out, "result.json"))
    dg = load(os.path.join(out, "diagnostics.json")) if os.path.isfile(os.path.join(out, "diagnostics.json")) else {"diagnostics": [], "roots": []}
    D = {d["id"]: d for d in dg["diagnostics"]}
    roots = [D[i] for i in dg["roots"] if i in D]
    gold = g["roots"]
    hit = {}
    for gr in gold:
        for d in roots:
            if match(gr, d):
                hit[gr["id"]] = d["id"]
                break
    used = set(hit.values())
    matched_roots = [d for d in roots if d["id"] in used or any(match(gr, d) for gr in gold)]
    pkg_ok = [gr["id"] for gr in gold if gr.get("expect_package") and hit.get(gr["id"]) and D[hit[gr["id"]]].get("needs_package") == gr["expect_package"]]
    pkg_n = sum(1 for gr in gold if gr.get("expect_package"))
    # baselines from the same final-pass log
    logp = os.path.join(out, "build_logs")
    logt = ""
    if os.path.isdir(logp):
        for f in os.listdir(logp):
            if f.endswith(".log"):
                with open(os.path.join(logp, f), encoding="utf-8", errors="replace") as fh:
                    logt = fh.read()
    main_dir = os.path.dirname(res.get("build", {}).get("main") or "") if res.get("build") else ""
    raw = raw_log_errors(logt, main_dir)
    b1 = raw[:1]
    b1_hit = one_to_one(gold, b1)
    b2_hit = one_to_one(gold, raw)
    b2_prec = (sum(1 for d in raw if any(loc_match(gr, d) for gr in gold)) / len(raw)) if raw else None
    row = {"case": cid, "set": g.get("set", "dev"), "gold_roots": len(gold), "reported_roots": len(roots), "root_hits": len(hit), "root_recall": len(hit) / len(gold) if gold else None,
           "root_precision": (len(matched_roots) / len(roots)) if roots else None, "missed": [gr["id"] + ":" + gr["class"] + "@" + str(gr.get("file")) + ":" + str(gr.get("line")) for gr in gold if gr["id"] not in hit],
           "package_named_correctly": "%d/%d" % (len(pkg_ok), pkg_n), "log_errors_raw": len(raw), "status_before": res.get("status"),
           "baseline_first_error_recall": len(b1_hit) / len(gold) if gold else None, "baseline_all_log_errors_recall": len(b2_hit) / len(gold) if gold else None,
           "baseline_all_log_errors_precision": b2_prec, "build_seconds_before": round(t_build, 2), "init_exit": r0.returncode, "build_exit_before": r1.returncode}
    # fix + rebuild
    if g.get("fix") is not None:
        src = os.path.join(work, "src")
        apply_fix(src, g["fix"])
        with open(os.path.join(work, "changes.json"), "w", encoding="utf-8") as fh:
            json.dump(g.get("changes", {}), fh, ensure_ascii=False, indent=1)
        t0 = time.time()
        r2 = py([os.path.join(S, "lx_build.py"), "--work", work, "--out", out, "--quiet"] + extra)
        res2 = load(os.path.join(out, "result.json"))
        dg2 = load(os.path.join(out, "diagnostics.json"))
        aud = [d for d in dg2["diagnostics"] if d.get("source") == "audit"]
        rep = res2["build"]["reproducibility"]
        remaining = ["%s:%s" % (d["class"], d.get("key") or d.get("name") or d.get("file")) for d in dg2["diagnostics"] if d["severity"] == "error" and not d.get("cascade_of")]
        row.update({"status_after_fix": res2["status"], "expect_status": g.get("expect_status", "success"), "status_ok": res2["status"] == g.get("expect_status", "success"),
                    "remaining_after_fix": remaining, "expected_remaining": g.get("expect_remaining", []),
                    "remaining_ok": sorted(remaining) == sorted(g.get("expect_remaining", [])) if "expect_remaining" in g else not remaining,
                    "audit_flags_after_fix": [d["class"] for d in aud if d["severity"] != "info"], "engine_passes": res2["build"]["engine_passes"],
                    "converged": res2["build"]["converged"], "repro_checked": rep.get("checked"), "byte_identical": rep.get("byte_identical"),
                    "build_seconds_after": round(time.time() - t0, 2), "build_exit_after": r2.returncode, "pdf_pages": res2["artifacts"].get("pdf_pages")})
        # mutation probes on top of the fixed project
        probes = []
        for k, mu in enumerate(g.get("mutations", [])):
            mwork = os.path.join(base, "mut%d" % k)
            shutil.copytree(work, mwork, ignore=shutil.ignore_patterns("build", "build_repro"))
            apply_fix(os.path.join(mwork, "src"), mu["fix"])
            if "changes" in mu:
                with open(os.path.join(mwork, "changes.json"), "w", encoding="utf-8") as fh:
                    json.dump(mu["changes"], fh, ensure_ascii=False, indent=1)
            py([os.path.join(S, "lx_build.py"), "--work", mwork, "--out", os.path.join(base, "mut%d_out" % k), "--quiet", "--no-repro"] + extra)
            dm = load(os.path.join(base, "mut%d_out" % k, "diagnostics.json"))
            fired = sorted({d["class"] for d in dm["diagnostics"] if d["severity"] in ("warning", "error") and d.get("source") in ("audit", "static", "log")} )
            probes.append({"probe": mu["name"], "expect": mu["expect"], "caught": mu["expect"] in fired, "fired": fired})
            if not keep:
                shutil.rmtree(mwork, ignore_errors=True)
                shutil.rmtree(os.path.join(base, "mut%d_out" % k), ignore_errors=True)
        row["mutation_probes"] = probes
    if not keep:
        for d in ("build", "build_repro"):
            shutil.rmtree(os.path.join(work, d), ignore_errors=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all")
    ap.add_argument("--cases")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", default=os.path.join(RES, "cases"))
    a = ap.parse_args()
    ids = sorted(f[:-5] for f in os.listdir(GOLD) if f.endswith(".json"))
    if a.cases:
        ids = [i for i in ids if i in a.cases.split(",")]
    rows = []
    for cid in ids:
        g = load(os.path.join(GOLD, cid + ".json"))
        if a.set != "all" and g.get("set", "dev") != a.set:
            continue
        print("==", cid, flush=True)
        try:
            rows.append(run_case(cid, a.keep, a.out))
        except Exception as e:  # keep evaluating other cases
            rows.append({"case": cid, "set": g.get("set", "dev"), "error": repr(e)})
        print(json.dumps(rows[-1], ensure_ascii=False)[:600], flush=True)
    sets = {}
    for s in ("dev", "holdout"):
        R = [r for r in rows if r.get("set") == s and "error" not in r]
        if not R:
            continue
        G = sum(r["gold_roots"] for r in R)
        P = [p for r in R for p in r.get("mutation_probes", [])]
        sets[s] = {"cases": [r["case"] for r in R], "gold_roots": G,
                   "root_recall": sum(r["root_hits"] for r in R) / G,
                   "root_precision": sum(r["root_precision"] * r["reported_roots"] for r in R if r["root_precision"] is not None) / max(1, sum(r["reported_roots"] for r in R)),
                   "reported_roots": sum(r["reported_roots"] for r in R), "raw_log_errors": sum(r["log_errors_raw"] for r in R),
                   "baseline_first_error_recall": sum(r["baseline_first_error_recall"] * r["gold_roots"] for r in R) / G,
                   "baseline_all_log_errors_recall": sum(r["baseline_all_log_errors_recall"] * r["gold_roots"] for r in R) / G,
                   "fix_status_ok": "%d/%d" % (sum(1 for r in R if r.get("status_ok")), sum(1 for r in R if "status_ok" in r)),
                   "remaining_ok": "%d/%d" % (sum(1 for r in R if r.get("remaining_ok")), sum(1 for r in R if "remaining_ok" in r)),
                   "byte_identical_rebuilds": "%d/%d" % (sum(1 for r in R if r.get("byte_identical")), sum(1 for r in R if r.get("repro_checked"))),
                   "audit_clean_after_documented_fix": "%d/%d" % (sum(1 for r in R if r.get("audit_flags_after_fix") == []), sum(1 for r in R if "audit_flags_after_fix" in r)),
                   "mutation_probes_caught": "%d/%d" % (sum(1 for p in P if p["caught"]), len(P)),
                   "missed": [m for r in R for m in r["missed"]]}
    m = {"generated_by": "tests/run_eval.py", "sets": sets, "errors": [r for r in rows if "error" in r]}
    os.makedirs(RES, exist_ok=True)
    tag = "" if a.set == "all" and not a.cases else "_" + (a.cases or a.set).replace(",", "_")
    with open(os.path.join(RES, "metrics%s.json" % tag), "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "eval_rows%s.json" % tag), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "commands%s.json" % tag), "w", encoding="utf-8") as fh:
        json.dump(COMMANDS, fh, ensure_ascii=False, indent=1)
    print(json.dumps(sets, ensure_ascii=False, indent=1))
    return 0 if not m["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
