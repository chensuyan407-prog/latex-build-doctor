#!/usr/bin/env python3
"""Initialise a LaTeX case: copy the input project to a working copy, find the main file, engine, bib tool,
check that every class / package / .bst / font / \\input / graphic exists BEFORE the first compile.

  python lx_init.py --case /input/case.json --out /app/output --work /app/work [--src DIR] [--main FILE] [--engine E]

Writes work/state.json, work/orig/ (untouched snapshot), work/src/ (edit here), work/changes.json (template),
output/result.json (status not_built). Prints a short project map for the agent.
"""
import argparse
import datetime as dt
import os
import re
import shutil
import sys
import tarfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lx_common import (SRC_EXT, VERSION, contract_fields, detect_bibtool, detect_engine, find_mains, font_lookup, inspect_cls, iter_files, kpsewhich_many,
                       load_json, parse_tex_file, read_text, rel, resolve_graphic, resolve_tex, summarize_case, which, write_json, AUX_EXT, GRAPHIC_EXT, TEX_EXT)

TEXT_MATERIAL = (".md", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".bib", ".tex", ".rst", ".xml", ".html", ".log")


def resolve_ci(target, bases, root, exts=("",)):
    """Case-insensitive fallback lookup (for Linux) returning relative path from root if found, else None."""
    t = target.strip().strip('"').replace("\\", "/")
    cands = [t + e for e in exts] if not os.path.splitext(t)[1] or exts == ("",) else [t]
    for base in bases:
        for c in cands:
            parts = [p for p in os.path.normpath(os.path.join(os.path.relpath(base, root), c)).split(os.sep) if p and p != "."]
            if any(p == ".." for p in parts):
                continue
            cur = root
            real = []
            ok = True
            for part in parts:
                try:
                    names = os.listdir(cur)
                except OSError:
                    ok = False
                    break
                if part in names:
                    real.append(part)
                else:
                    alt = [x for x in names if x.lower() == part.lower()]
                    if not alt:
                        ok = False
                        break
                    real.append(alt[0])
                cur = os.path.join(cur, real[-1])
            if ok and os.path.isfile(cur):
                return "/".join(real)
    return None


def safe_extract(archive, dest):
    os.makedirs(dest, exist_ok=True)
    base = os.path.realpath(dest)
    names = []
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                t = os.path.realpath(os.path.join(dest, m.filename))
                if not t.startswith(base) or m.filename.startswith("/"):
                    continue
                z.extract(m, dest)
                names.append(m.filename)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                p = os.path.realpath(os.path.join(dest, m.name))
                if not p.startswith(base) or m.issym() or m.islnk() or not (m.isfile() or m.isdir()):
                    continue
                t.extract(m, dest)
                names.append(m.name)
    return names


def copy_tree(src, dst, skip_aux=True):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst, exist_ok=True)
    n = 0
    for p in iter_files(src):
        r = os.path.relpath(p, src)
        b = os.path.basename(p).lower()
        if skip_aux and (b.endswith(AUX_EXT) or b.endswith(".pdf") and os.path.splitext(b)[0] + ".tex" in [x.lower() for x in os.listdir(os.path.dirname(p))]):
            continue
        q = os.path.join(dst, r)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(p, q)
        n += 1
    return n


def project_scan(src, main_hint=None):
    files_info, texts = {}, {}
    for p in iter_files(src):
        if p.lower().endswith(TEX_EXT):
            try:
                inf, text, lines = parse_tex_file(p, src)
            except OSError:
                continue
            files_info[inf["path"]] = inf
    mains = find_mains(src, files_info)
    roots = {}
    for f, inf in files_info.items():
        r = inf["magic"].get("root")
        if r and not inf.get("documentclass"):
            roots[f] = os.path.normpath(os.path.join(os.path.dirname(f), r)).replace(os.sep, "/")
    main = None
    if main_hint:
        mh = main_hint.replace("\\", "/")
        main = mh if mh in files_info else next((m for m in files_info if m.endswith(mh)), None)
        return files_info, mains, main, roots
    if not main and roots:
        counts = {}
        for target in roots.values():
            if target in mains:
                counts[target] = counts.get(target, 0) + 1
        if counts:
            main = max(mains, key=lambda m: (counts.get(m, 0), -mains.index(m)))
    if not main and mains:
        main = mains[0]
    return files_info, mains, main, roots


def reach(src, main, files_info):
    """Files reached from main via \\input/\\include (+ problems)."""
    order, problems, seen = [], [], set()
    main_dir = os.path.join(src, os.path.dirname(main))

    def visit(f, depth):
        if f in seen or depth > 30:
            return
        seen.add(f)
        order.append(f)
        inf = files_info.get(f)
        if not inf:
            return
        for inc in inf["includes"]:
            p = resolve_tex(inc["target"], main_dir, src) or resolve_tex(inc["target"], os.path.join(src, os.path.dirname(f)), src)
            bad_case = case_mismatch(p, src) if p else resolve_ci(inc["target"], [main_dir, os.path.join(src, os.path.dirname(f)), src], src, TEX_EXT + ("",))
            if bad_case:
                problems.append({"class": "missing_file", "severity": "error", "file": f, "line": inc["line"],
                                 "message": "\\%s{%s} matches %s only case-insensitively" % (inc["cmd"], inc["target"], bad_case),
                                 "hint": "Works on Windows/macOS, fails on Linux: use the exact path/case %s." % bad_case, "source": "precheck", "name": inc["target"], "actual": bad_case})
            if not p:
                if not bad_case:
                    problems.append({"class": "missing_file", "severity": "error", "file": f, "line": inc["line"], "message": "\\%s{%s}: file not found" % (inc["cmd"], inc["target"]),
                                     "hint": "Path is resolved relative to the MAIN file directory; check spelling/case/extension.", "source": "precheck", "name": inc["target"]})
                continue
            r = rel(p, src)
            if r.lower().endswith(TEX_EXT) or r.endswith((".tikz", ".pgf")):
                if r not in files_info and r.lower().endswith(TEX_EXT):
                    try:
                        files_info[r] = parse_tex_file(p, src)[0]
                    except OSError:
                        pass
                visit(r, depth + 1)

    visit(main, 0)
    return order, problems


def case_mismatch(path, root):
    """Return the real relative path if `path` exists only with different letter case (case-insensitive FS), else None."""
    rp = os.path.relpath(path, root)
    if rp.startswith(".."):
        return None
    cur, real, bad = root, [], False
    for part in rp.split(os.sep):
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        if part in names:
            real.append(part)
        else:
            alt = [x for x in names if x.lower() == part.lower()]
            if not alt:
                return None
            real.append(alt[0])
            bad = True
        cur = os.path.join(cur, real[-1])
    return "/".join(real) if bad else None


def precheck(src, main, order, files_info, engine, bibtool):
    """Classes, packages, bst, bib, graphics, fonts exist? -> problems list + environment facts."""
    problems = []
    main_dir = os.path.join(src, os.path.dirname(main))
    local = {os.path.basename(p).lower(): rel(p, src) for p in iter_files(src)}
    need = {}
    cls = (files_info[main].get("documentclass") or {})
    if cls.get("name"):
        need[cls["name"] + ".cls"] = (main, cls["line"], "class")
    for f in order:
        inf = files_info.get(f, {})
        for p in inf.get("packages", []):
            need.setdefault(p["name"] + ".sty", (f, p["line"], "package"))
        for b in inf.get("bibstyle", []):
            if b["style"]:
                need.setdefault(b["style"] + ".bst", (f, b["line"], "bst"))
    in_main = {x.lower() for x in os.listdir(main_dir)} if os.path.isdir(main_dir) else set()
    not_local = [n for n in need if n.lower() not in in_main and not os.path.isfile(os.path.join(main_dir, n))]
    found, have_kpse = kpsewhich_many(not_local, cwd=main_dir)
    missing = []
    for n, (f, ln, kind) in need.items():
        if n.lower() in in_main or os.path.isfile(os.path.join(main_dir, n)):
            continue
        bname = os.path.basename(n)
        if bname.lower() in local and n not in found:
            where = local[bname.lower()]
            problems.append({"class": {"class": "missing_class", "package": "missing_package", "bst": "bib_missing_file"}[kind], "severity": "error", "file": f, "line": ln,
                             "message": "%s %s exists at %s but TeX only searches the main file's directory and the TeX tree" % (kind, n, where), "name": os.path.splitext(bname)[0], "found_at": where,
                             "hint": "Copy %s next to %s (keep the template file unchanged), or set TEXINPUTS=./%s//: - copying is more portable." % (where, main, os.path.dirname(where)), "source": "precheck"})
            continue
        if not have_kpse:
            continue
        if n not in found:
            missing.append(n)
            cls_ = {"class": "missing_class", "package": "missing_package", "bst": "bib_missing_file"}[kind]
            problems.append({"class": cls_, "severity": "error", "file": f, "line": ln, "message": "%s %s not found (not in the project, not in the TeX installation)" % (kind, n), "name": os.path.splitext(n)[0],
                             "hint": {"class": "Template class missing: put the template's .cls (from the journal/school template package) next to the main file. Do not replace the class without approval.",
                                      "package": "Package not installed: install it (tlmgr install), ship the .sty with the project, or remove it if unused (check which commands need it).",
                                      "bst": "Bibliography style missing: ship the template's .bst or use a standard style the template allows."}[kind], "source": "precheck"})
    # bib files
    bibs = []
    for f in order:
        for b in files_info.get(f, {}).get("bibs", []):
            t = b["target"]
            cand = [t] if t.endswith(".bib") else [t + ".bib", t]
            hit = None
            for c in cand:
                for base in (main_dir, src):
                    pp = os.path.normpath(os.path.join(base, c))
                    if os.path.isfile(pp):
                        hit = rel(pp, src)
                        break
                if hit:
                    break
            if not hit:
                kf, _ = kpsewhich_many([cand[0]], cwd=main_dir)
                if kf:
                    hit = kf[cand[0]]
            if hit and b["cmd"] in ("addbibresource", "addglobalbib") and not t.lower().endswith(".bib"):
                problems.append({"class": "bib_missing_file", "severity": "error", "file": f, "line": b["line"], "message": "\\%s{%s}: biblatex needs the full file name" % (b["cmd"], t),
                                 "hint": "Write \\%s{%s.bib} - biber looks for the literal name and finds no data source." % (b["cmd"], t), "source": "precheck", "name": t})
            if hit:
                bibs.append(hit)
            else:
                ci_bib = resolve_ci(t, [main_dir, src], src, (".bib", ""))
                if ci_bib:
                    problems.append({"class": "bib_missing_file", "severity": "error", "file": f, "line": b["line"], "message": "bibliography file %s matches %s only case-insensitively" % (t, ci_bib),
                                     "hint": "Use exact case %s (Linux is case-sensitive)." % ci_bib, "source": "precheck", "name": t, "actual": ci_bib})
                else:
                    problems.append({"class": "bib_missing_file", "severity": "error", "file": f, "line": b["line"], "message": "bibliography file %s not found" % t,
                                     "hint": ("\\addbibresource needs the .bib extension; " if b["cmd"] == "addbibresource" and not t.endswith(".bib") else "") + "check the file name / path.", "source": "precheck", "name": t})
    # graphics
    for f in order:
        inf = files_info.get(f, {})
        gp = []
        for g in order:
            gp += files_info.get(g, {}).get("graphicspath", [])
        for g in inf.get("graphics", []):
            if "#" in g["target"] or "\\" in g["target"]:
                continue
            gpath = resolve_graphic(g["target"], main_dir, src, gp)
            bad_case = case_mismatch(gpath, src) if gpath else resolve_ci(g["target"], [main_dir, src] + [os.path.join(main_dir, x) for x in gp], src, GRAPHIC_EXT + ("",))
            if bad_case:
                problems.append({"class": "missing_file", "severity": "error", "file": f, "line": g["line"], "message": "graphic %s matches %s only case-insensitively" % (g["target"], bad_case),
                                 "hint": "Works on Windows/macOS, fails on Linux (case-sensitive): use the exact name %s in \\includegraphics (do not rename shared assets silently)." % bad_case,
                                 "source": "precheck", "name": g["target"], "actual": bad_case})
            elif not gpath:
                problems.append({"class": "missing_file", "severity": "error", "file": f, "line": g["line"], "message": "graphic %s not found" % g["target"],
                                 "hint": "Check path, case and extension (relative to the main file or \\graphicspath). If the figure is not in the materials, do not fabricate one: use a clearly marked placeholder (\\fbox / draft) and list it under needs_confirmation.",
                                 "source": "precheck", "name": g["target"]})
    # fonts
    fonts = sorted({x["font"] for f in order for x in files_info.get(f, {}).get("fonts", []) if x["font"]})
    fres, fc = font_lookup(fonts)
    for name, ok in fres.items():
        if ok is False:
            loc = next(((f, x["line"]) for f in order for x in files_info.get(f, {}).get("fonts", []) if x["font"] == name), (main, None))
            problems.append({"class": "missing_font", "severity": "error", "file": loc[0], "line": loc[1], "message": "font '%s' not found by fc-list" % name, "font": name,
                             "hint": "Install the font, ship it with the project (Path=./fonts/, Extension=.otf), or switch to an installed font (record the substitution; templates may mandate the font).", "source": "precheck"})
    # engine/tool availability
    for tool in [engine] + ([bibtool] if bibtool else []):
        if not which(tool):
            problems.append({"class": "missing_tool", "severity": "error", "file": None, "line": None, "message": "%s is not on PATH" % tool,
                             "hint": "Install TeX Live / MiKTeX with %s, or choose another engine (--engine)." % tool, "source": "precheck"})
    return problems, bibs, missing, fonts, fres


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="/input/case.json")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--src", help="project directory (default: the case.json directory)")
    ap.add_argument("--main", help="main .tex (relative to the project)")
    ap.add_argument("--engine", choices=["pdflatex", "xelatex", "lualatex", "latex", "platex", "uplatex"])
    ap.add_argument("--keep-src", action="store_true", help="do not overwrite an existing work/src (re-scan only)")
    a = ap.parse_args()
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    case = load_json(a.case, {}) if a.case and os.path.isfile(a.case) else {}
    if a.case and not os.path.isfile(a.case):
        print("WARN case file not found:", a.case)
    if not isinstance(case, dict):
        case = {"_raw": case}
    cid, contract = summarize_case(case)
    from lx_common import extract_contract_schema
    fields, req_fields, prop_schemas = extract_contract_schema(contract)
    in_dir = os.path.abspath(a.src or (os.path.dirname(os.path.abspath(a.case)) if a.case else "."))
    # extract archives into work/extracted
    stage = os.path.join(work, "_stage")
    if not (a.keep_src and os.path.isdir(os.path.join(work, "src"))):
        if os.path.isdir(stage):
            shutil.rmtree(stage)
        copy_tree(in_dir, stage, skip_aux=False)
        for p in list(iter_files(stage)):
            if p.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2")):
                names = safe_extract(p, os.path.splitext(p)[0].replace(".tar", "") + "_extracted")
                if names:
                    os.remove(p)
        # never treat the case description itself as a project file
        materials = []
        for p in iter_files(stage):
            r = rel(p, stage)
            pl = p.lower()
            if pl.endswith(TEXT_MATERIAL) or (pl.endswith(".pdf") and os.path.splitext(os.path.basename(pl))[0] + ".tex" not in [x.lower() for x in os.listdir(os.path.dirname(p))]):
                materials.append(r)
        copy_tree(stage, os.path.join(work, "orig"), skip_aux=False)
        copy_tree(stage, os.path.join(work, "src"), skip_aux=True)
        for f in ("case.json", "task.md"):
            p = os.path.join(work, "src", f)
            if os.path.isfile(p):
                os.remove(p)
        shutil.rmtree(stage, ignore_errors=True)
    else:
        materials = [rel(p, os.path.join(work, "orig")) for p in iter_files(os.path.join(work, "orig")) if p.lower().endswith(TEXT_MATERIAL + (".pdf",))]
    src = os.path.join(work, "src")
    files_info, mains, main, roots = project_scan(src, a.main)
    st = {"skill_version": VERSION, "case_id": cid, "case_file": os.path.abspath(a.case) if a.case else None, "input_dir": in_dir,
          "contract_fields": fields, "contract_required": req_fields, "contract_properties": prop_schemas,
          "materials": materials, "mains": mains, "main": main, "created": dt.datetime.now(dt.timezone.utc).isoformat()}
    if a.main and not main:
        print("ERROR explicit --main '%s' not found in %s" % (a.main, sorted(files_info) or "none"))
        st.update({"engine": a.engine or "pdflatex", "bibtool": None, "order": [], "problems": []})
        write_json(os.path.join(work, "state.json"), st)
        write_skeletons(work, out, st, failed_reason="explicit --main '%s' not found" % a.main)
        return 2
    print("latex-build-doctor %s init" % VERSION)
    print("case_id:", cid, "| contract fields:", fields or "(none found - result.json gets the standard fields)")
    print("input dir:", in_dir, "| %d files copied to work/src (edit there), snapshot in work/orig" % sum(1 for _ in iter_files(src)))
    non_tex_mats = [m for m in materials if m not in ("case.json",) and not m.lower().endswith(TEX_EXT)]
    if non_tex_mats:
        print("materials (%d): %s" % (len(non_tex_mats), ", ".join(non_tex_mats[:20])))
    local_cls = [p for p in iter_files(src) if p.lower().endswith(".cls")]
    for cp in local_cls[:4]:
        ci = inspect_cls(cp)
        print("local template %s: base=%s options=%s cmds=%s checks=%s" % (rel(cp, src), ci["base_class"], ci["options"][:8], ci["commands"][:12], ci["checks"][:4]))
    task = os.path.join(in_dir, "task.md")
    if os.path.isfile(task):
        print("task file:", task, "(read it fully)")
    if main and re.match(r"^(?:template|templates|examples?)/", main, re.I):
        print("NOTE: detected main '%s' is inside a template/example folder. If writing a new manuscript, create work/src/main.tex and build with --main main.tex." % main)
    if not main:
        print("NO MAIN FILE: no .tex with \\documentclass + \\begin{document}.", "tex files:", sorted(files_info) or "none")
        print("If the task is to write a new document: create work/src/main.tex, then run lx_build.py --main main.tex")
        st.update({"engine": a.engine or "pdflatex", "bibtool": None, "order": [], "problems": []})
        write_json(os.path.join(work, "state.json"), st)
        write_skeletons(work, out, st)
        return 0
    order, problems = reach(src, main, files_info)
    engine, why = (a.engine, "--engine") if a.engine else detect_engine(files_info[main], [files_info[f] for f in order if f in files_info])
    bibtool, bwhy = detect_bibtool([files_info[f] for f in order if f in files_info])
    p2, bibs, missing, fonts, fres = precheck(src, main, order, files_info, engine, bibtool)
    problems += p2
    unreached = sorted(f for f in files_info if f not in order and f not in mains)
    cls = files_info[main].get("documentclass") or {}
    st.update({"engine": engine, "engine_reason": why, "bibtool": bibtool, "bibtool_reason": bwhy, "order": order, "bibs": bibs, "documentclass": cls,
               "unreached_tex": unreached, "fonts": fonts, "fonts_found": fres, "problems": problems, "other_mains": mains[1:]})
    write_json(os.path.join(work, "state.json"), st)
    write_skeletons(work, out, st)
    print("main: %s  (other candidates: %s)" % (main, ", ".join(m for m in mains if m != main) or "none"))
    print("class: %s [%s]  engine: %s (%s)  bib: %s (%s)" % (cls.get("name"), ",".join(cls.get("options", [])), engine, why, bibtool, bwhy))
    print("files reached from main (%d): %s" % (len(order), ", ".join(order[:25]) + (" ..." if len(order) > 25 else "")))
    if unreached:
        print("tex files NOT reached from main:", ", ".join(unreached[:15]))
    if bibs:
        print("bib files:", ", ".join(bibs))
    if fonts:
        print("fonts:", ", ".join("%s=%s" % (k, {True: "ok", False: "MISSING", None: "unchecked"}[v]) for k, v in fres.items()))
    if problems:
        print("PRECHECK problems (%d) - fix or confirm before compiling:" % len(problems))
        for p in problems[:30]:
            print("  %s %s:%s %s -> %s" % (p["class"], p.get("file"), p.get("line"), p["message"], p.get("hint", "")))
    else:
        print("precheck: all classes, packages, bib files, graphics and fonts found")
    print("next: python lx_build.py --work %s --out %s" % (work, out))
    return 0


def write_skeletons(work, out, st, failed_reason=None):
    ch = os.path.join(work, "changes.json")
    if not os.path.isfile(ch):
        write_json(ch, {"_doc": "Record every source edit: file, line (in the NEW file), from, to, reason, fixes (diagnostic id or task item), type. "
                                "requirements = template/task items to verify by regex; needs_confirmation = items a human must decide; fields = contract overrides.",
                        "changes": [], "requirements": [], "needs_confirmation": [], "notes": [], "fields": {}})
    res_path = os.path.join(out, "result.json")
    existing = load_json(res_path, None)
    if isinstance(existing, dict) and existing.get("status") in ("success", "partial") and not failed_reason:
        return
    res = {"case_id": st.get("case_id"), "status": "failed" if failed_reason else "not_built", "skill": "latex-build-doctor " + VERSION,
           "note": failed_reason or "initialised only - run lx_build.py to compile and fill this file"}
    for f in st.get("contract_fields") or []:
        res.setdefault(f, None)
    write_json(res_path, res)


if __name__ == "__main__":
    sys.exit(main())
