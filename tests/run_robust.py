#!/usr/bin/env python3
"""Robustness checks for latex-build-doctor: python tests/run_robust.py -> execution/results/robustness.json"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "submission", "scripts")
OUT = os.path.join(ROOT, "execution", "results", "robustness")
CMDS = []


def py(args, env=None, timeout=600):
    t0 = time.time()
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env=env or dict(os.environ, PYTHONIOENCODING="utf-8"))
    CMDS.append({"argv": [os.path.relpath(a, ROOT).replace(os.sep, "/") if os.path.isabs(a) and a.startswith(ROOT) else a for a in args], "exit": r.returncode,
                 "seconds": round(time.time() - t0, 2), "stdout_tail": r.stdout[-800:], "stderr_tail": r.stderr[-500:]})
    return r


def case(name, files, binary=None):
    d = os.path.join(OUT, name)
    shutil.rmtree(d, ignore_errors=True)
    inp = os.path.join(d, "input")
    os.makedirs(inp)
    for f, t in files.items():
        p = os.path.join(inp, f)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if isinstance(t, bytes):
            open(p, "wb").write(t)
        else:
            open(p, "w", encoding="utf-8", newline="\n").write(t)
    return d, inp


def init_build(d, inp, init_extra=(), build_extra=(), env=None):
    r0 = py([os.path.join(S, "lx_init.py"), "--case", os.path.join(inp, "case.json"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output")] + list(init_extra), env=env)
    r1 = py([os.path.join(S, "lx_build.py"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output"), "--quiet"] + list(build_extra), env=env)
    res = json.load(open(os.path.join(d, "output", "result.json"), encoding="utf-8"))
    dg = os.path.join(d, "output", "diagnostics.json")
    diags = json.load(open(dg, encoding="utf-8"))["diagnostics"] if os.path.isfile(dg) else []
    return r0, r1, res, diags


CASE = '{"case_id": "%s", "output_contract": {"status": "", "pdf": ""}}'
DOC = "\\documentclass{article}\n\\begin{document}\n%s\n\\end{document}\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, "-", detail[:200], flush=True)

    # 1 no main file
    d, inp = case("no_main", {"case.json": CASE % "no_main", "notes.md": "# only notes\n"})
    r0, r1, res, D = init_build(d, inp)
    check("no_main_file", r0.returncode == 0 and r1.returncode == 2 and res["status"] == "failed" and "status" in res and "pdf" in res,
          "init exit %d, build exit %d, status %s" % (r0.returncode, r1.returncode, res["status"]))
    # 2 two mains, choose with --main
    d, inp = case("two_mains", {"case.json": CASE % "two_mains", "main.tex": DOC % "Main.", "supplement.tex": DOC % "Supp."})
    r0, r1, res, D = init_build(d, inp, init_extra=["--main", "supplement.tex"])
    check("two_mains_select", res["build"]["main"] == "supplement.tex" and res["status"] == "success" and "main.tex" in r0.stdout,
          "chosen %s, status %s" % (res["build"]["main"], res["status"]))
    # 3 infinite loop -> timeout
    d, inp = case("infinite_loop", {"case.json": CASE % "infinite_loop", "main.tex": DOC % "\\def\\x{\\x}\\x"})
    r0, r1, res, D = init_build(d, inp, build_extra=["--timeout", "8", "--budget", "30"])
    roots = res["diagnostics_summary"]["root_causes"]
    check("infinite_loop_timeout", any(x["class"] == "timeout" for x in roots) and res["status"] in ("failed", "partial"),
          "roots %s, status %s, %.1f s" % ([x["class"] for x in roots], res["status"], res["build"]["seconds"]))
    # 4 missing TeX tools (PATH without TeX)
    d, inp = case("no_tex_on_path", {"case.json": CASE % "no_tex", "main.tex": DOC % "Hello."})
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PATH=os.path.dirname(sys.executable))
    r0, r1, res, D = init_build(d, inp, env=env)
    check("missing_tool", any(x["class"] == "missing_tool" for x in D) and r1.returncode == 2 and res["status"] == "failed",
          "classes %s, exit %d" % (sorted({x['class'] for x in D}), r1.returncode))
    # 5 zip input
    d, inp = case("zip_input", {"case.json": CASE % "zip_input"})
    with zipfile.ZipFile(os.path.join(inp, "project.zip"), "w") as z:
        z.writestr("paper/main.tex", DOC % "Zipped \\input{sec}.")
        z.writestr("paper/sec.tex", "section text")
        z.writestr("../evil.tex", "path traversal")
    r0, r1, res, D = init_build(d, inp)
    check("zip_input", res["status"] == "success" and res["build"]["main"].endswith("paper/main.tex") and not os.path.exists(os.path.join(d, "work", "evil.tex")),
          "main %s, status %s, traversal entry skipped" % (res["build"]["main"], res["status"]))
    # 6 broken changes.json
    d, inp = case("broken_changes", {"case.json": CASE % "broken_changes", "main.tex": DOC % "Text."})
    py([os.path.join(S, "lx_init.py"), "--case", os.path.join(inp, "case.json"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output")])
    open(os.path.join(d, "work", "changes.json"), "w").write('{"changes": [{"file": "main.tex", "to": "\\x"}')
    r1 = py([os.path.join(S, "lx_build.py"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output"), "--quiet"])
    D = json.load(open(os.path.join(d, "output", "diagnostics.json"), encoding="utf-8"))["diagnostics"]
    check("broken_changes_json", any(x["class"] == "changes_json_invalid" for x in D) and r1.returncode in (0, 1),
          "classes %s exit %d" % (sorted({x['class'] for x in D}), r1.returncode))
    # 7 missing glyphs (XeLaTeX, Latin Modern, Chinese text)
    d, inp = case("missing_glyph", {"case.json": CASE % "missing_glyph", "main.tex": "\\documentclass{article}\n\\usepackage{fontspec}\n\\begin{document}\nResult 结果 ok.\n\\end{document}\n"})
    r0, r1, res, D = init_build(d, inp)
    check("missing_glyph", res["diagnostics_summary"]["missing_glyphs"] and res["status"] == "partial" and any("glyph" in u for u in res["uncertainty"]),
          "glyphs %s, engine %s" % (res["diagnostics_summary"]["missing_glyphs"], res["build"]["engine"]))
    # 8 missing package
    d, inp = case("missing_package", {"case.json": CASE % "missing_package", "main.tex": "\\documentclass{article}\n\\usepackage{nosuchpkgxyz}\n\\begin{document}\n\\nosuchcmd{}\n\\end{document}\n"})
    r0, r1, res, D = init_build(d, inp)
    roots = res["diagnostics_summary"]["root_causes"]
    check("missing_package", roots and roots[0]["class"] == "missing_package" and roots[0]["line"] == 2 and "PRECHECK" in r0.stdout and any("not known yet" in u for u in res["uncertainty"]),
          "first root %s:%s, %d roots" % (roots[0]["class"] if roots else None, roots[0].get("line") if roots else None, len(roots)))
    # 9 GB18030 source (non-UTF-8) under pdfLaTeX, ASCII-only commands: reported encoding, no crash
    d, inp = case("gb18030_input", {"case.json": CASE % "gb18030", "main.tex": (DOC % "% \u6ce8\u91ca comment\nText.").encode("gb18030")})
    r0, r1, res, D = init_build(d, inp)
    st = json.load(open(os.path.join(d, "work", "state.json"), encoding="utf-8"))
    check("non_utf8_input", r1.returncode in (0, 1) and res["status"] in ("success", "partial"), "status %s exit %d" % (res["status"], r1.returncode))
    # 10 deterministic diagnostics on rebuild
    d0 = os.path.join(ROOT, "execution", "results", "cases", "dev_multi")
    if os.path.isdir(os.path.join(d0, "work")):
        a = os.path.join(OUT, "det_a")
        b = os.path.join(OUT, "det_b")
        for o in (a, b):
            py([os.path.join(S, "lx_build.py"), "--work", os.path.join(d0, "work"), "--out", o, "--quiet", "--no-repro"])
        ja = json.load(open(os.path.join(a, "diagnostics.json"), encoding="utf-8"))
        jb = json.load(open(os.path.join(b, "diagnostics.json"), encoding="utf-8"))
        pa = open(os.path.join(a, "main.pdf"), "rb").read() if os.path.isfile(os.path.join(a, "main.pdf")) else b""
        pb = open(os.path.join(b, "main.pdf"), "rb").read() if os.path.isfile(os.path.join(b, "main.pdf")) else b""
        check("deterministic_rebuild", ja == jb and pa == pb and pa, "diagnostics identical %s, PDF identical %s" % (ja == jb, pa == pb))
    # 11 \today document: byte-identical within the same day
    d, inp = case("today_repro", {"case.json": CASE % "today", "main.tex": DOC % "Built \\today."})
    r0, r1, res, D = init_build(d, inp)
    rp = res["build"]["reproducibility"]
    check("source_date_epoch_repro", rp.get("checked") and rp.get("byte_identical"), json.dumps(rp)[:200])

    # 12 v0.2 regression: URL %, double-opt cite, nested matrix in tabular, bib \" & %, <argument> cs, map_field
    c12 = json.dumps({
        "case_id": "v02_reg",
        "output_contract": {
            "fixed_source": "path", "tex_source": "path", "source": "path",
            "unresolved_citations": "list", "open_questions": "list", "compile_status": "str"
        }
    })
    bib12 = '% @article{commented_out, title = {Ignored}}\n@article{schr2020,\n  author = {Doe, J.},\n  title = {Schr\\"odinger Cat},\n  journal = {J. Phys.},\n  year = {2020}\n}\n'
    tex12 = (
        "\\documentclass{article}\n\\usepackage{url,amsmath,natbib}\n\\begin{document}\n"
        "See \\url{https://example.com/a%20b} and \\cite[see][p.~2]{schr2020,missing2021}.\n"
        "\\begin{tabular}{ll} A & $\\begin{pmatrix}1 & 2 \\\\ 3 & 4\\end{pmatrix}$ \\\\ \\end{tabular}\n"
        "\\begin{figure}\\caption{Value \\SI{5}{nm}}\\end{figure}\n"
        "\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}\n"
    )
    d, inp = case("v02_regression", {"case.json": c12, "main.tex": tex12, "refs.bib": bib12})
    r0, r1, res, D = init_build(d, inp, build_extra=["--no-repro"])
    classes = {x["class"] for x in D}
    si_roots = [x for x in D if x.get("cs") == "\\SI"]
    mf_ok = (
        all(res.get(field) == "src/main.tex" for field in ("fixed_source", "tex_source", "source"))
        and res.get("output_contract") == {
            field: res.get(field) for field in json.loads(c12)["output_contract"]
        }
        and "missing2021" in (res.get("unresolved_citations") or [])
        and isinstance(res.get("open_questions"), list)
        and res.get("compile_status") in ("partial", "failed", "success")
    )
    check(
        "v02_parser_and_contract",
        ("brace" not in classes) and ("table_columns" not in classes) and ("bib_syntax" not in classes)
        and any(x.get("key") == "missing2021" for x in D) and bool(si_roots) and mf_ok,
        "classes=%s si_cs=%s mf_ok=%s" % (sorted(classes), [x.get("cs") for x in si_roots], mf_ok),
    )

    # 13 lx_record --auto & lx_table --width longtable
    d, inp = case("v02_tools", {"case.json": CASE % "v02_tools", "main.tex": DOC % "Hello.", "data.csv": "Method,RMSE\nBase,0.42\nOurs,0.28\n"})
    py([os.path.join(S, "lx_init.py"), "--case", os.path.join(inp, "case.json"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output")])
    rt = py([os.path.join(S, "lx_table.py"), os.path.join(inp, "data.csv"), "--width", "longtable", "--caption", "Results", "--label", "tab:res", "--out", os.path.join(d, "work", "src", "tab.tex")])
    open(os.path.join(d, "work", "src", "main.tex"), "w", encoding="utf-8").write("\\documentclass{article}\n\\usepackage{booktabs,longtable}\n\\begin{document}\n\\input{tab}\n\\end{document}\n")
    rr = py([os.path.join(S, "lx_record.py"), "--work", os.path.join(d, "work"), "--auto", "--reason", "add data table", "--type", "table"])
    r1 = py([os.path.join(S, "lx_build.py"), "--work", os.path.join(d, "work"), "--out", os.path.join(d, "output"), "--quiet", "--no-repro"])
    res_t = json.load(open(os.path.join(d, "output", "result.json"), encoding="utf-8"))
    dg_t = json.load(open(os.path.join(d, "output", "diagnostics.json"), encoding="utf-8"))["diagnostics"]
    aud_warns = [x for x in dg_t if x.get("source") == "audit" and x.get("severity") != "info"]
    check("v02_record_and_longtable", rt.returncode == 0 and rr.returncode == 0 and r1.returncode == 0 and res_t["status"] == "success" and not aud_warns,
          "status=%s aud=%s" % (res_t["status"], aud_warns))
    json.dump({"checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks)}, open(os.path.join(ROOT, "execution", "results", "robustness.json"), "w", encoding="utf-8"), indent=1)
    json.dump(CMDS, open(os.path.join(ROOT, "execution", "results", "commands_robustness.json"), "w", encoding="utf-8"), indent=1)
    for sub in os.listdir(OUT):
        for w in ("work/build", "work/build_repro"):
            shutil.rmtree(os.path.join(OUT, sub, w), ignore_errors=True)
    print("%d/%d passed" % (sum(c["passed"] for c in checks), len(checks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
