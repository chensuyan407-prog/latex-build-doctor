#!/usr/bin/env python3
"""Compile the working copy, diagnose, audit edits and write all deliverables.

  python lx_build.py --work /app/work --out /app/output [--main F] [--engine E] [--passes 5] [--timeout 180]
                     [--no-repro] [--shell-escape] [--quiet]

Each run: fresh copy work/src -> work/build, engine pass 1 -> bibtex/biber (+makeindex) -> passes until no rerun
request (max --passes) -> parse .log/.blg -> static checks -> diff vs work/orig + check against work/changes.json
-> second clean build with the same SOURCE_DATE_EPOCH to test byte-reproducibility -> write output/.
Exit 0 = success (PDF, no errors, no undefined refs/cites, converged, requirements met); 1 = PDF but problems remain; 2 = no PDF.
"""
import argparse
import datetime as dt
import difflib
import json
import os
import platform
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lx_common import (AUX_EXT, TEX_EXT, VERSION, code_lines, detect_bibtool, detect_engine, extract_pdf_text, iter_files, load_json, read_text, rel, run, sha256_file,
                       tex_env, tool_version, which, write_json, write_text, load_rules)
from lx_init import project_scan, reach, precheck
from lx_log import ROOT_RANK, parse_biber_blg, parse_bibtex_blg, parse_tex_log
from lx_static import cite_checks, package_checks, parse_bib, scan_project

EPOCH_DEFAULT = "1704067200"  # 2024-01-01T00:00:00Z, recorded in BUILD.md
RERUN = re.compile(r"Rerun to get|Label\(s\) may have changed|Please rerun LaTeX|rerunfilecheck Warning: File `[^']+' has changed|Package natbib Warning: Citation\(s\) may have changed|There were undefined references.*Rerun|Table widths have changed\. Rerun|Package longtable Warning: Column widths have changed")
BIBER_RERUN = re.compile(r"Please \(re\)run Biber|Package biblatex Warning: Please \(re\)run Biber")
NUM = re.compile(r"(?<![A-Za-z\\\d.])[-−]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?")
CASE_FILES = {"case.json", "task.md"}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def copy_src(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)
    for p in iter_files(src):
        r = os.path.relpath(p, src)
        b = os.path.basename(p)
        if r in CASE_FILES or b.lower().endswith(AUX_EXT):
            continue
        q = os.path.join(dst, r)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(p, q)


def compile_once(bdir, main_rel, engine, bibtool, passes, timeout, shell_escape, epoch, budget_s):
    """Run the build sequence in bdir. Returns dict with rounds, logs, pdf path."""
    main_dir = os.path.join(bdir, os.path.dirname(main_rel))
    job = os.path.splitext(os.path.basename(main_rel))[0]
    env = tex_env({"SOURCE_DATE_EPOCH": epoch})
    dvi_engine = engine in ("latex", "platex", "uplatex")
    # XeTeX (and DVI engines) stamp "XeTeX output YYYY.MM.DD:HHMM" into the DVI/PDF Creator, ignoring SOURCE_DATE_EPOCH
    stamp = ["-output-comment=%s" % engine] if engine in ("xelatex", "latex", "platex", "uplatex") else []
    cmd = [engine, "-interaction=nonstopmode", "-file-line-error", "-recorder"] + stamp + (["-shell-escape"] if shell_escape else ["-no-shell-escape"]) + [os.path.basename(main_rel)]
    rounds = []
    t_start = time.time()

    def go(c, label):
        t0 = time.time()
        left = max(10, budget_s - (time.time() - t_start))
        code, out, err = run(c, cwd=main_dir, timeout=min(timeout, left), env=env)
        aux = os.path.join(main_dir, job + ".aux")
        rounds.append({"step": label, "cmd": " ".join(c), "exit": code, "seconds": round(time.time() - t0, 2),
                       "aux_sha256": sha256_file(aux) if os.path.isfile(aux) else None, "timeout": code == 124, "stderr_tail": err[-300:] if err else ""})
        return code, out

    def logtext():
        p = os.path.join(main_dir, job + ".log")
        return read_log(p)

    def toc_hash():
        h = []
        for ext in (".toc", ".lof", ".lot"):
            p = os.path.join(main_dir, job + ext)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                h.append(sha256_file(p))
        return tuple(h)

    toc0 = toc_hash()
    code, out = go(cmd, "%s pass 1" % engine)
    log = logtext()
    pdf_name = job + (".dvi" if dvi_engine else ".pdf")
    fatal_first = not os.path.isfile(os.path.join(main_dir, pdf_name)) or code == 124
    n_eng = 1
    bib_ran = None
    if not fatal_first or bibtool:
        aux = os.path.join(main_dir, job + ".aux")
        auxt = read_text(aux)[0] if os.path.isfile(aux) else ""
        sub_bib_aux = [p for p in iter_files(main_dir) if p.endswith(".aux") and p != aux and "\\bibdata" in read_text(p)[0]]
        need_bibtex = bibtool == "bibtex" and ("\\bibdata" in auxt or bool(sub_bib_aux))
        need_biber = bibtool == "biber" and os.path.isfile(os.path.join(main_dir, job + ".bcf"))
        if need_bibtex and which("bibtex"):
            if "\\bibdata" in auxt:
                go(["bibtex", job], "bibtex")
            for sp in sub_bib_aux:
                go(["bibtex", os.path.relpath(sp, main_dir)[:-4]], "bibtex (%s)" % os.path.basename(sp))
            bib_ran = "bibtex"
        elif need_biber and which("biber"):
            go(["biber", job], "biber")
            bib_ran = "biber"
        idx = os.path.join(main_dir, job + ".idx")
        if os.path.isfile(idx) and os.path.getsize(idx) > 0 and which("makeindex"):
            go(["makeindex", job + ".idx"], "makeindex")
        nlo = os.path.join(main_dir, job + ".nlo")
        if os.path.isfile(nlo) and which("makeindex"):
            go(["makeindex", job + ".nlo", "-s", "nomencl.ist", "-o", job + ".nls"], "makeindex nomencl")
        if os.path.isfile(os.path.join(main_dir, job + ".glo")) and which("makeglossaries"):
            go(["makeglossaries", job], "makeglossaries")
        need_more = bool(bib_ran) or bool(RERUN.search(log)) or os.path.isfile(idx) or (toc_hash() != toc0)
        biber_again = False
        while n_eng < passes and (need_more or biber_again):
            if time.time() - t_start > budget_s:
                rounds.append({"step": "stopped", "cmd": "", "exit": None, "seconds": 0, "note": "build budget exhausted"})
                break
            n_eng += 1
            code, out = go(cmd, "%s pass %d" % (engine, n_eng))
            if code == 124:
                break
            log = logtext()
            need_more = bool(RERUN.search(log))
            if bib_ran == "biber" and BIBER_RERUN.search(log) and not biber_again:
                go(["biber", job], "biber (rerun)")
                biber_again = True
                need_more = True
            elif biber_again:
                biber_again = False
            if not need_more and len(rounds) >= 2 and rounds[-1].get("aux_sha256") and rounds[-1]["aux_sha256"] != _last_engine_aux(rounds[:-1]):
                need_more = True  # aux still changing
    if dvi_engine and os.path.isfile(os.path.join(main_dir, job + ".dvi")) and which("dvipdfmx"):
        go(["dvipdfmx", job + ".dvi"], "dvipdfmx")
    log = logtext()
    pdf = os.path.join(main_dir, job + ".pdf")
    eng_rounds = [r for r in rounds if r["step"].startswith(engine + " pass")]
    converged = not RERUN.search(log) and (len(eng_rounds) < 2 or eng_rounds[-1]["aux_sha256"] == eng_rounds[-2]["aux_sha256"])
    blg = os.path.join(main_dir, job + ".blg")
    return {"rounds": rounds, "log": log, "blg": read_log(blg), "bib_ran": bib_ran,
            "pdf": pdf if os.path.isfile(pdf) else None, "engine_passes": n_eng, "converged": converged and n_eng < passes + 1,
            "timeout": any(r.get("timeout") for r in rounds), "main_dir": main_dir, "job": job, "cmd": cmd,
            "fls": os.path.join(main_dir, job + ".fls"), "seconds": round(time.time() - t_start, 2)}


def read_log(p):
    """TeX logs are UTF-8 with occasional raw 8-bit bytes: decode per byte sequence, never re-guess the whole file."""
    if not os.path.isfile(p):
        return ""
    with open(p, "rb") as fh:
        return fh.read().decode("utf-8", "replace")


def _last_engine_aux(rs):
    for r in reversed(rs):
        if " pass " in r["step"]:
            return r.get("aux_sha256")
    return None


# ---------------------------------------------------------------- diff + change audit


def numbers(s):
    return [x.replace("−", "-") for x in NUM.findall(s)]


def diff_project(orig, src):
    """Hunks per text file between work/orig and work/src."""
    hunks = []
    files = set()
    for base in (orig, src):
        if os.path.isdir(base):
            for p in iter_files(base):
                r = rel(p, base)
                if r not in CASE_FILES and not os.path.basename(p).lower().endswith(AUX_EXT):
                    files.add(r)
    patch = []
    for r in sorted(files):
        a, b = os.path.join(orig, r), os.path.join(src, r)
        ta = read_text(a)[0] if os.path.isfile(a) else None
        tb = read_text(b)[0] if os.path.isfile(b) else None
        if not r.lower().endswith(TEX_EXT + (".bib", ".cls", ".sty", ".bst", ".md", ".txt", ".csv", ".tikz", ".cfg", ".json")):
            if (ta is None) != (tb is None) or (os.path.isfile(a) and os.path.isfile(b) and sha256_file(a) != sha256_file(b)):
                hunks.append({"file": r, "kind": "binary_or_other", "old_start": None, "new_start": None, "old": "", "new": "",
                              "added": tb is not None and ta is None, "deleted": ta is not None and tb is None})
            continue
        if ta == tb:
            continue
        la = (ta or "").split("\n")
        lb = (tb or "").split("\n")
        ud = list(difflib.unified_diff(la, lb, "a/" + r, "b/" + r, n=1, lineterm=""))
        patch += ud
        sm = difflib.SequenceMatcher(None, la, lb, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            hunks.append({"file": r, "kind": tag if ta is not None else "new_file", "old_start": i1 + 1, "old_end": i2, "new_start": j1 + 1, "new_end": j2,
                          "old": "\n".join(la[i1:i2]), "new": "\n".join(lb[j1:j2])})
    return hunks, "\n".join(patch) + ("\n" if patch else "")


def audit_changes(hunks, records):
    """Every hunk needs a record; records must match a hunk; facts (numbers, cite/ref/label keys) must not drift silently."""
    findings = []
    used = set()
    for k, h in enumerate(hunks):
        h["id"] = "H%03d" % (k + 1)
        match = []
        for j, r in enumerate(records):
            if r.get("file", "").replace("\\", "/") != h["file"]:
                continue
            fr, to = r.get("from") or "", r.get("to") or ""
            ln = r.get("line")
            hit = False
            if to and to.strip() and to.strip() in h["new"]:
                hit = True
            elif fr and fr.strip() and fr.strip() in h["old"]:
                hit = True
            elif isinstance(ln, int) and h.get("new_start") and h["new_start"] - 1 <= ln <= max(h.get("new_end") or 0, h["new_start"]) + 1:
                hit = True
            elif h["kind"] in ("new_file", "binary_or_other") and (r.get("type") in ("new_file", "add_file", "asset") or not fr):
                hit = True
            if hit:
                match.append(j)
                used.add(j)
        h["records"] = match
        if not match:
            findings.append({"class": "undocumented_change", "severity": "warning", "file": h["file"], "line": h.get("new_start"), "source": "audit",
                             "message": "%s change at %s:%s has no record in changes.json" % (h["kind"], h["file"], h.get("new_start")),
                             "hint": "Add {file, line, from, to, reason, fixes} for this edit (or revert it)."})
        if h["kind"] in ("replace", "delete", "insert"):
            on, nn = sorted(numbers(_body(h["old"]))), sorted(numbers(_body(h["new"])))
            if on != nn:
                acc = any(records[j].get("accept_numbers") for j in match)
                lost = _multiset_minus(on, nn)
                new = _multiset_minus(nn, on)
                if lost or new:
                    findings.append({"class": "number_changed", "severity": "info" if acc else "warning", "file": h["file"], "line": h.get("new_start"), "source": "audit",
                                     "message": "numbers changed in this edit: removed %s added %s" % (lost[:8], new[:8]), "accepted": acc,
                                     "hint": "Values must match the source material. If intended (e.g. fixing a typo against the source), set accept_numbers:true and cite the source in reason."})
            fam = {"citation": r"\\(?:[cC]ite\w*|[pP]arencite|[tT]extcite|[aA]utocite|footcite|supercite|nocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}",
                   "reference": r"\\(?:ref|eqref|pageref|autoref|[cC]ref|vref|nameref|labelcref)\*?\{([^}]*)\}", "label": r"\\label\{([^}]*)\}"}
            for cmd, rx in fam.items():
                ko = {k.strip() for g in re.findall(rx, h["old"]) for k in g.split(",")}
                kn = {k.strip() for g in re.findall(rx, h["new"]) for k in g.split(",")}
                if ko != kn and ko:
                    acc = any(records[j].get("accept_keys") for j in match)
                    findings.append({"class": "key_changed", "severity": "info" if acc else "warning", "file": h["file"], "line": h.get("new_start"), "source": "audit",
                                     "message": "\\%s keys changed: %s -> %s" % (cmd, sorted(ko), sorted(kn)), "accepted": acc,
                                     "hint": "Changing which work/label is referenced changes meaning; confirm against the source (accept_keys:true with reason)."})
    for j, r in enumerate(records):
        if j not in used:
            findings.append({"class": "stale_record", "severity": "warning", "file": r.get("file"), "line": r.get("line"), "source": "audit",
                             "message": "change record %d (%s) matches no edit in the diff" % (j + 1, (r.get("reason") or "")[:60]),
                             "hint": "Fix file/from/to/line of the record, or delete it if the edit was reverted."})
    return findings


def _body(s):
    return "\n".join(code_lines(s))


def _multiset_minus(a, b):
    b = list(b)
    out = []
    for x in a:
        if x in b:
            b.remove(x)
        else:
            out.append(x)
    return out


def source_numbers(orig_root, materials):
    nums = set()
    for m in materials:
        p = os.path.join(orig_root, m)
        if os.path.isfile(p):
            try:
                txt = extract_pdf_text(p) if p.lower().endswith(".pdf") else read_text(p)[0]
                nums.update(_canon(x) for x in numbers(txt))
            except OSError:
                pass
    return nums


def _canon(x):
    x = x.replace(",", "") if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", x) else x.replace(",", ".")
    try:
        v = float(x)
        return ("%.10g" % v)
    except ValueError:
        return x


def new_numbers(src_root, files, srcnums):
    """Numbers in the document body that appear in no input material (fabrication guard)."""
    out = []
    for f in files:
        p = os.path.join(src_root, f)
        if not os.path.isfile(p):
            continue
        lines = code_lines(read_text(p)[0])
        in_body = not any("\\documentclass" in l for l in lines)
        for ln, line in enumerate(lines, 1):
            if "\\begin{document}" in line:
                in_body = True
                continue
            if not in_body:
                continue
            t = re.sub(r"https?://\S+|\b10\.\d{4,9}/[^\s}]+", " ", line)
            t = re.sub(r"\[[^\]]*\]", " ", t)
            t = re.sub(r"\\(?:cmidrule|cline)\s*(?:\([^)]*\))?\s*\{[^}]*\}", " ", t)
            t = re.sub(r"\\(?:multicolumn|multirow|fontsize|setcounter|addtocounter|renewcommand|providecommand)\b\*?\s*(?:\{[^}]*\}\s*){1,3}", " ", t)
            t = re.sub(r"\\(?:begin|end|label|ref|eqref|cref|Cref|cite\w*|parencite\w*|textcite\w*|autocite\w*|includegraphics|input|include|vspace|hspace|setlength|addlinespace|rule|resizebox|scalebox|makebox|parbox|columnwidth|linewidth|textwidth|url|href|bibliography\w*|cellcolor|rowcolor|color|textcolor|arraystretch|tabcolsep|selectfont|SI\w*|qty\w*)\b\*?(\{[^}]*\})?", " ", t)
            t = re.sub(r"\d+(?:\.\d+)?\s*(?:pt|em|ex|cm|mm|in|bp|sp|\\(?:linewidth|textwidth|columnwidth|textheight|baselineskip))", " ", t)
            t = re.sub(r"\{[lcrpXS|@{}\d.\s*mb<>!]+\}", " ", t) if ("tabular" in line or "\\begin{" in line) else t
            for x in numbers(t):
                c = _canon(x)
                if c not in srcnums and len(x.strip("-−")) > 1 and not re.fullmatch(r"(19|20)\d\d", x):
                    out.append({"file": f, "line": ln, "number": x})
    return out


# ---------------------------------------------------------------- requirements / templates


def check_requirements(src_root, main_rel, order, reqs, cls_name):
    text = ""
    for f in order:
        p = os.path.join(src_root, f)
        if os.path.isfile(p):
            text += "\n".join(code_lines(read_text(p)[0])) + "\n"
    tmpl = load_rules("templates.json")
    items = []
    for r in tmpl.get(cls_name, {}).get("required", []) + tmpl.get("*", {}).get("required", []):
        items.append(dict(r, origin="template:%s" % (cls_name if r in tmpl.get(cls_name, {}).get("required", []) else "*")))
    for r in reqs or []:
        items.append(dict(r, origin="changes.json"))
    res = []
    for k, r in enumerate(items):
        pat = r.get("pattern")
        ok = None
        try:
            if r.get("only_if") and not re.search(r["only_if"], text, re.S | re.M):
                continue
        except re.error:
            pass
        if pat:
            try:
                ok = bool(re.search(pat, text, re.S | re.M))
            except re.error as e:
                ok = None
                r["error"] = str(e)
        if r.get("absent"):
            ok = (not ok) if ok is not None else None
        res.append({"id": r.get("id") or "T%02d" % (k + 1), "desc": r.get("desc", pat), "pattern": pat, "ok": ok, "severity": r.get("severity", "error"), "origin": r["origin"]})
    return res


# ---------------------------------------------------------------- environment


def environment(engine, bibtool, info, fls, src_root, main_dir, pdf):
    env = {"recorded_at": now(), "os": platform.platform(), "python": platform.python_version(),
           "engine": {"name": engine, "version": tool_version(engine), "banner": info.get("engine_banner", "")[:200]},
           "bibtool": {"name": bibtool, "version": tool_version(bibtool)} if bibtool else None,
           "kpsewhich": tool_version("kpsewhich"),
           "documentclass": info.get("documentclass"), "packages": info.get("packages", {}), "project_files_used": [], "distribution_files_used": 0}
    m = re.search(r"\(TeX Live (\d{4})[^)]*\)|MiKTeX[- ]?([\d.]+)", env["engine"]["version"] or "") or re.search(r"\(TeX Live (\d{4})[^)]*\)|MiKTeX[- ]?([\d.]+)", info.get("engine_banner", ""))
    env["distribution"] = ("TeX Live " + m.group(1)) if m and m.group(1) else (("MiKTeX " + m.group(2)) if m else "unknown")
    if os.path.isfile(fls):
        used = set()
        n_dist = 0
        for line in read_text(fls)[0].splitlines():
            if line.startswith("INPUT "):
                p = line[6:].strip()
                ap = os.path.normpath(os.path.join(main_dir, p)) if not os.path.isabs(p) else os.path.normpath(p)
                if ap.startswith(os.path.normpath(main_dir)) or not os.path.isabs(p):
                    r = rel(ap, src_root)
                    if not r.lower().endswith(AUX_EXT) and not r.startswith(".."):
                        used.add(r)
                else:
                    n_dist += 1
        env["project_files_used"] = sorted(used)
        env["distribution_files_used"] = n_dist
    if pdf and which("pdffonts"):
        code, out, err = run(["pdffonts", pdf], timeout=30)
        fonts = []
        for line in out.splitlines()[2:]:
            parts = line.split()
            if parts:
                fonts.append({"name": parts[0], "type": " ".join(parts[1:-5]) if len(parts) > 6 else parts[1], "embedded": parts[-5] if len(parts) >= 6 else "?"})
        env["pdf_fonts"] = fonts
        env["pdf_fonts_not_embedded"] = [f["name"] for f in fonts if f["embedded"] == "no"]
    if pdf and which("pdfinfo"):
        code, out, err = run(["pdfinfo", pdf], timeout=30)
        pi = {}
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                pi[k.strip()] = v.strip()
        env["pdf_info"] = {k: pi.get(k) for k in ("Pages", "Page size", "PDF version", "Producer", "Creator") if k in pi}
    return env


def previews(pdf, outdir, max_pages=8):
    if not pdf or not which("pdftoppm"):
        return []
    os.makedirs(outdir, exist_ok=True)
    for p in os.listdir(outdir):
        if p.startswith("page-"):
            os.remove(os.path.join(outdir, p))
    run(["pdftoppm", "-png", "-r", "100", "-f", "1", "-l", str(max_pages), pdf, os.path.join(outdir, "page")], timeout=120)
    return sorted(p for p in os.listdir(outdir) if p.endswith(".png"))


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--main")
    ap.add_argument("--engine", choices=["pdflatex", "xelatex", "lualatex", "latex", "platex", "uplatex"])
    ap.add_argument("--passes", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=180, help="seconds per tool call")
    ap.add_argument("--budget", type=int, default=420, help="seconds for the whole build sequence")
    ap.add_argument("--no-repro", action="store_true", help="skip the second clean build")
    ap.add_argument("--shell-escape", action="store_true")
    ap.add_argument("--epoch", default=None, help="SOURCE_DATE_EPOCH (default %s)" % EPOCH_DEFAULT)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--max-show", type=int, default=25)
    a = ap.parse_args()
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    st = load_json(os.path.join(work, "state.json"), {}) or {}
    src, orig = os.path.join(work, "src"), os.path.join(work, "orig")
    if not os.path.isdir(src):
        print("ERROR no work/src - run lx_init.py first (or create work/src/main.tex)")
        return 2
    changes = load_json(os.path.join(work, "changes.json"), {}) or {}
    if not isinstance(changes, dict):
        changes = {}
    bad_changes = changes == {} and os.path.isfile(os.path.join(work, "changes.json"))
    hint_main = a.main or changes.get("main") or st.get("main")
    if not a.main and not changes.get("main") and hint_main and re.match(r"^(?:template|templates|examples?)/", hint_main, re.I):
        root_mains = [m for m in os.listdir(src) if m.lower().endswith(TEX_EXT) and os.path.isfile(os.path.join(src, m))]
        if root_mains:
            hint_main = None  # prefer newly created root-level main file over template sample
    files_info, mains, main_rel, roots = project_scan(src, hint_main)
    t0 = time.time()
    diags = []
    if bad_changes:
        diags.append({"class": "changes_json_invalid", "severity": "warning", "file": "work/changes.json", "line": None, "source": "audit",
                      "message": "work/changes.json is not valid JSON - change records ignored", "hint": "Fix the JSON (escape backslashes as \\\\)."})
    if not main_rel:
        res = {"case_id": st.get("case_id"), "status": "failed", "skill": "latex-build-doctor " + VERSION, "error": "no main .tex (\\documentclass + \\begin{document}) in work/src",
               "uncertainty": ["nothing compiled"]}
        for f in st.get("contract_fields") or []:
            res.setdefault(f, None)
        write_json(os.path.join(out, "result.json"), res)
        print("FAILED: no main file in work/src. Create one or pass --main.")
        return 2
    order, pre = reach(src, main_rel, files_info)
    infos = [files_info[f] for f in order if f in files_info]
    engine = a.engine or changes.get("engine") or (st.get("engine") if st.get("main") == main_rel and st.get("engine_reason") == "--engine" else None) or detect_engine(files_info[main_rel], infos)[0]
    bibtool = detect_bibtool(infos)[0]
    p2, bibs, missing, fonts, fres = precheck(src, main_rel, order, files_info, engine, bibtool)
    pre += p2
    epoch = a.epoch or changes.get("source_date_epoch") or EPOCH_DEFAULT
    bdir = os.path.join(work, "build")
    copy_src(src, bdir)
    R = compile_once(bdir, main_rel, engine, bibtool, a.passes, a.timeout, a.shell_escape or changes.get("shell_escape", False), str(epoch), a.budget)
    main_dir_rel = os.path.dirname(main_rel)
    proj_files_main = [os.path.relpath(os.path.join(src, f), os.path.join(src, main_dir_rel)).replace(os.sep, "/") for f in files_info] + \
                      [os.path.relpath(os.path.join(src, b), os.path.join(src, main_dir_rel)).replace(os.sep, "/") for b in bibs]
    loaded = {p["name"] for inf in infos for p in inf["packages"]}
    static, ctx = scan_project(src, order, main_rel, engine)
    defined = ctx["newcommands"]
    logd, info = parse_tex_log(R["log"], proj_files_main, loaded, defined)
    if R["pdf"] and not any(d["class"] == "missing_font" for d in logd):
        for d in pre:
            if d["class"] == "missing_font":
                d["severity"] = "info"
                d["message"] += " (fc-list did not index it, but compiler loaded fonts cleanly)"
    for d in logd:
        if d.get("file"):
            p = os.path.normpath(os.path.join(main_dir_rel, d["file"])).replace(os.sep, "/")
            d["file"] = p if os.path.isfile(os.path.join(src, p)) else d["file"]
        d["source"] = "log"
    # errors raised inside a .sty/.cls: attribute them to the project line that loads that package/class
    cls_info = files_info[main_rel].get("documentclass") or {}
    for d in logd:
        ri = d.get("raised_in")
        m = re.search(r"(?:Package|Class) ([\w@.-]+) Error", d.get("message", ""))
        name = (os.path.splitext(ri)[0] if ri else None) or (m.group(1) if m else None)
        if not name or (d.get("line") and d.get("file") and not ri):
            continue
        if cls_info.get("name") == name or (m and cls_info.get("name") == m.group(1)):
            d["file"], d["line"] = main_rel, cls_info.get("line")
            d["attributed_to"] = "\\documentclass{%s}" % cls_info.get("name")
            continue
        for p in ctx["packages"]:
            if p["name"] in (name, m.group(1) if m else None):
                d["file"], d["line"] = p["file"], p["line"]
                d["attributed_to"] = "\\usepackage{%s}" % p["name"]
                break
    for d in logd:
        if d["class"] == "missing_glyph" and not d.get("line"):
            ch = (d.get("char") or "").split(" (U+")[0]
            for f in order:
                t = ctx["texts"].get(f)
                if ch and t:
                    for k, l in enumerate(t[0].split("\n"), 1):
                        if ch in l:
                            d["file"], d["line"] = f, k
                            break
                if d.get("line"):
                    break
    if R["timeout"]:
        last = [d for d in logd if d.get("file")]
        logd.insert(0, {"class": "timeout", "severity": "error", "source": "log", "file": (last[-1]["file"] if last else main_rel), "line": last[-1].get("line") if last else None,
                        "message": "compiler did not finish within %ss (infinite loop / recursion or waiting for input)" % a.timeout,
                        "hint": "Look at the last file/line in the log tail: a macro that calls itself, \\loop without exit, or a missing file prompt."})
    bibd = []
    if R["bib_ran"] == "bibtex":
        bibd = parse_bibtex_blg(R["blg"], bibs)
    elif R["bib_ran"] == "biber":
        bibd = parse_biber_blg(R["blg"], bibs)
    for d in bibd:
        d["source"] = R["bib_ran"]
    bibentries, bibf = {}, []
    for b in bibs:
        p = os.path.join(src, b)
        if os.path.isfile(p):
            e, f = parse_bib(p, b)
            bibentries.update(e)
            bibf += f
    thebib = []
    for f in order:
        t = "\n".join(ctx["texts"].get(f, ("", []))[1])
        thebib += re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}", t)
    citef = cite_checks(ctx["cites"], bibentries, thebib) if (bibs or thebib) else [
        {"class": "undefined_cite", "severity": "error", "file": f, "line": ln, "message": "\\%s{%s} but no bibliography (\\bibliography / \\addbibresource / thebibliography)" % (c, k), "key": k, "source": "static",
         "hint": "Add the bibliography the template requires."} for k, f, ln, c in ctx["cites"]]
    pk = package_checks(ctx["packages"], engine, (files_info[main_rel].get("documentclass") or {}).get("name", ""))
    hunks, patch = diff_project(orig, src) if os.path.isdir(orig) else ([], "")
    audit = audit_changes(hunks, changes.get("changes") or [])
    srcnums = source_numbers(orig, st.get("materials") or [])
    if os.path.isdir(orig):
        for m in st.get("materials") or []:
            pass
    newnums = new_numbers(src, order, srcnums) if srcnums else []
    cls_name = (files_info[main_rel].get("documentclass") or {}).get("name", "")
    reqs = check_requirements(src, main_rel, order, changes.get("requirements"), cls_name)
    # merge + dedupe: log diagnostics are authoritative for compile errors; static adds location/explanations
    changed_lines = {(h["file"], ln) for h in hunks if h.get("new_start") for ln in range(h["new_start"], (h.get("new_end") or h["new_start"]) + 1)}
    fabd = [{"class": "number_not_in_materials", "severity": "warning", "source": "audit", "file": x["file"], "line": x["line"], "message": "number %s is not in any input material" % x["number"],
             "hint": "Numbers in the deliverable must come from the materials. Check the source; if it is a typo in the input, record it; never invent values.", "number": x["number"]}
            for x in newnums if (x["file"], x["line"]) in changed_lines or not os.path.isfile(os.path.join(orig, x["file"]))]
    reqd = [{"class": "requirement_failed", "severity": "error" if r["severity"] == "error" else "warning", "source": "static", "file": main_rel, "line": None,
             "message": "requirement %s not met: %s" % (r["id"], r["desc"]), "hint": "Origin %s; pattern %s" % (r["origin"], r["pattern"]), "key": r["id"]}
            for r in reqs if r["ok"] is False]
    allds = diags + pre + logd + bibd + static + bibf + citef + pk + audit + fabd + reqd
    seen = set()
    D = []
    for d in allds:
        key = (d["class"], d.get("file"), d.get("line"), d.get("key") or d.get("name") or d.get("cs") or d.get("message", "")[:60] if d["source"] != "log" else d.get("message", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        D.append(d)
    # static undefined_ref/cite duplicates of log warnings (same key) -> keep the log one, note static location
    logkeys = {(d["class"], d.get("key")) for d in logd + bibd if d.get("key")}
    D = [d for d in D if not (d["source"] in ("static",) and d["class"] in ("undefined_ref", "undefined_cite") and (d["class"], d.get("key")) in logkeys and d["severity"] == "error" and False)]
    k_e = k_w = 0
    for d in D:
        if d.get("source") != "log" or "id" not in d:
            if d["severity"] == "error":
                k_e += 1
                d["id"] = "S%03d" % k_e
            else:
                k_w += 1
                d["id"] = "N%03d" % k_w
        if d.get("file") and d.get("line"):
            p = os.path.join(src, d["file"])
            if os.path.isfile(p):
                try:
                    L = read_text(p)[0].split("\n")
                    d["source_line"] = L[d["line"] - 1].strip()[:200] if 0 < d["line"] <= len(L) else None
                except OSError:
                    pass
    link_origins(D)
    stat_bib = {(d.get("key"), (d.get("field") or "").split("|")[0]) for d in D if d["class"] == "bib_field" and d["source"] == "static"}
    D = [d for d in D if not (d["class"] == "bib_field" and d["source"] in ("bibtex", "biber") and (d.get("key"), d.get("field")) in stat_bib)]
    for d in D:
        if d.get("source") == "log" and d["class"] in ("missing_class", "missing_package", "missing_file", "missing_font", "bib_missing_file") and not d.get("cascade_of"):
            nm = os.path.splitext(os.path.basename((d.get("name") or d.get("font") or "").replace("\\", "/")))[0].lower()
            for p in D:
                if p.get("source") == "precheck" and p["class"] == d["class"] and nm and nm == os.path.splitext(os.path.basename((p.get("name") or p.get("font") or "").replace("\\", "/")))[0].lower():
                    d["cascade_of"] = p["id"]
                    break
    eng = [d for d in D if d["class"] == "engine_mismatch" and d.get("source") == "log"]
    if eng:
        e0 = eng[0]
        e0["hint"] = e0.get("hint", "") + " Engine used: %s (%s)." % (engine, "from the % !TEX program magic comment" if (files_info[main_rel].get("magic") or {}).get("program") else "auto-detected")
        for d in D:
            if d["class"] == "engine_mismatch" and d.get("source") != "log" and not d.get("cascade_of"):
                d["cascade_of"] = e0.get("cascade_of") or e0["id"]
    # a log alignment error and the static column count describe the same table: keep the log one as root
    for d in D:
        if d["class"] == "table_columns" and d["severity"] == "error":
            for e in D:
                if e.get("source") == "log" and e["class"] == "alignment" and e.get("file") == d.get("file") and e.get("line") in (d.get("rows") or []):
                    root = e.get("cascade_of") or e["id"]
                    d["cascade_of"] = root
                    e["static_detail"] = d["message"]
                    e["hint"] = d.get("hint", e.get("hint"))
                    break
    for d in D:
        if d["class"] in ("undefined_cs", "undefined_env") and d.get("source") == "log" and not d.get("cascade_of"):
            fol = [x.get("cs") or x.get("env") for x in D if x.get("cascade_of") == d["id"] and x["class"] in ("undefined_cs", "undefined_env")]
            fol = [x for x in dict.fromkeys(fol) if x and x != (d.get("cs") or d.get("env"))]
            if fol:
                d["also"] = fol
                d["hint"] = d.get("hint", "") + " Same cause for: %s." % ", ".join(fol)
    errors = [d for d in D if d["severity"] == "error"]
    roots_ = [d for d in errors if not d.get("cascade_of")]
    has_fol = {d.get("cascade_of") for d in D if d.get("cascade_of")}
    roots_.sort(key=lambda d: (0 if d["source"] in ("precheck", "log") or d["id"] in has_fol else 1, ROOT_RANK.get(d["class"], 5), d.get("file") or "", d.get("line") or 0))
    log_err = [d for d in logd if d["severity"] == "error"]
    bib_err = [d for d in bibd if d["severity"] == "error"]
    pre_case_err = [d for d in pre if d.get("actual")]
    float_err = [d for d in static if d["class"] == "float_label" and d["severity"] == "error"]
    undef_ref = sorted({d["key"] for d in logd if d["class"] == "undefined_ref"})
    if info.get("fatal"):
        undef_ref = sorted(set(undef_ref) | {d["key"] for d in static if d["class"] == "undefined_ref" and d.get("key")})
    undef_cite = sorted({d["key"] for d in logd + bibd if d["class"] == "undefined_cite"})
    if bib_err or info.get("fatal") or not R["bib_ran"]:
        undef_cite = sorted(set(undef_cite) | {d["key"] for d in citef if d.get("key")})
    overfull = [d for d in logd if d["class"] == "overfull_box"]
    glyphs = [d for d in logd if d["class"] == "missing_glyph"]
    req_fail = [r for r in reqs if r["ok"] is False and r["severity"] == "error"]
    # reproducibility
    repro = {"checked": False}
    use_shell_escape = a.shell_escape or changes.get("shell_escape", False)
    if R["pdf"] and not a.no_repro and not R["timeout"] and not log_err:
        b2 = os.path.join(work, "build_repro")
        copy_src(src, b2)
        R2 = compile_once(b2, main_rel, engine, bibtool, a.passes, a.timeout, use_shell_escape, str(epoch), a.budget)
        h1 = sha256_file(R["pdf"])
        h2 = sha256_file(R2["pdf"]) if R2["pdf"] else None
        repro = {"checked": True, "pdf_sha256_build1": h1, "pdf_sha256_build2": h2, "byte_identical": h1 == h2, "source_date_epoch": str(epoch),
                 "rounds_build2": [r["step"] for r in R2["rounds"]]}
        shutil.rmtree(b2, ignore_errors=True)
    status = "success"
    if not R["pdf"]:
        status = "failed"
    elif log_err or bib_err or pre_case_err or float_err or undef_ref or undef_cite or not R["converged"] or req_fail or R["timeout"] or glyphs:
        status = "partial"
    # ---------------- outputs
    os.makedirs(out, exist_ok=True)
    out_src = os.path.join(out, "src")
    copy_src(src, out_src)
    pdf_out = None
    if R["pdf"]:
        pdf_out = os.path.join(out, R["job"] + ".pdf")
        shutil.copy2(R["pdf"], pdf_out)
    elif os.path.isfile(os.path.join(out, R["job"] + ".pdf")):
        os.remove(os.path.join(out, R["job"] + ".pdf"))
    logdir = os.path.join(out, "build_logs")
    os.makedirs(logdir, exist_ok=True)
    write_text(os.path.join(logdir, R["job"] + ".log"), R["log"])
    if R["blg"]:
        write_text(os.path.join(logdir, R["job"] + ".blg"), R["blg"])
    prev = previews(pdf_out, os.path.join(out, "preview"))
    env = environment(engine, bibtool, info, R["fls"], bdir, R["main_dir"], R["pdf"])
    env["project_files_used"] = [p for p in env.get("project_files_used", []) if not p.startswith("..")]
    write_json(os.path.join(out, "environment.json"), env)
    cmds = [r["cmd"] for r in R["rounds"] if r.get("cmd")]
    write_build_files(out, main_rel, engine, bibtool, cmds, epoch, env, R, a.shell_escape)
    write_text(os.path.join(out, "changes.diff"), patch)
    recs = changes.get("changes") or []
    change_log = []
    for h in hunks:
        rr = [recs[j] for j in h["records"]]
        change_log.append({"hunk": h["id"], "file": h["file"], "kind": h["kind"], "old_lines": [h.get("old_start"), h.get("old_end")], "new_lines": [h.get("new_start"), h.get("new_end")],
                           "old": h["old"][:1500], "new": h["new"][:1500], "reasons": [r.get("reason") for r in rr], "fixes": [r.get("fixes") for r in rr if r.get("fixes")],
                           "types": [r.get("type") for r in rr if r.get("type")], "documented": bool(rr)})
    write_json(os.path.join(out, "change_log.json"), change_log)
    diag_out = {"status": status, "roots": [d["id"] for d in roots_], "diagnostics": D, "requirements": reqs, "new_numbers_not_in_materials": newnums[:200]}
    write_json(os.path.join(out, "diagnostics.json"), diag_out)
    nc = (changes.get("needs_confirmation") or []) + [{"item": "numbers not found in any input material", "where": "%s:%s" % (x["file"], x["line"]), "value": x["number"]} for x in newnums[:30]]
    nc += [{"item": "requirement unknown/failed: " + r["desc"], "where": r["origin"]} for r in reqs if r["ok"] is not True and r["severity"] == "error"]
    unc = []
    if info.get("fatal"):
        unc.append("TeX stopped at a fatal error: errors after that point are not known yet - fix the root causes and rebuild")
    if not R["converged"]:
        unc.append("cross-references did not converge within %d passes" % a.passes)
    if repro.get("checked") and not repro.get("byte_identical"):
        unc.append("two clean builds gave different PDF bytes (non-deterministic content: \\today without SOURCE_DATE_EPOCH support, random numbers, timestamps)")
    if not repro.get("checked"):
        unc.append("byte-reproducibility not tested (build failed, errors remain or --no-repro)")
    if glyphs:
        unc.append("%d missing glyph(s) in the PDF (characters not in font)" % len(glyphs))
    if env.get("pdf_fonts_not_embedded"):
        unc.append("non-embedded PDF fonts: " + ", ".join(env["pdf_fonts_not_embedded"][:10]))
    if pdf_out:
        ptxt = extract_pdf_text(pdf_out)
        if "\ufffd" in ptxt:
            unc.append("replacement character (U+FFFD) found in extracted PDF text")
    if any(r["ok"] is None for r in reqs):
        unc.append("some requirements could not be checked automatically")
    und = [d for d in audit if d["class"] == "undocumented_change"]
    if und:
        unc.append("%d source change(s) without a change record" % len(und))
    summary = "%s: %s with %s, %d engine pass(es)%s; %d error(s) in log (%d root cause(s) overall), %d undefined ref(s), %d undefined citation(s), %d overfull box(es) >1pt; %d edit hunk(s), %d documented." % (
        status.upper(), main_rel, engine, R["engine_passes"], (" + " + R["bib_ran"]) if R["bib_ran"] else "", len(log_err), len(roots_), len(undef_ref), len(undef_cite), len(overfull),
        len(hunks), sum(1 for h in hunks if h["records"]))
    res = {
        "case_id": st.get("case_id"), "status": status, "summary": summary, "skill": "latex-build-doctor " + VERSION, "built_at": now(),
        "artifacts": {"source_dir": "src/", "main_tex": "src/" + main_rel, "pdf": (R["job"] + ".pdf") if pdf_out else None, "pdf_sha256": sha256_file(pdf_out) if pdf_out else None,
                      "pdf_pages": info.get("pdf_pages"), "previews": ["preview/" + p for p in prev], "diff": "changes.diff", "change_log": "change_log.json",
                      "diagnostics": "diagnostics.json", "build_report": "build_report.md", "build_instructions": "BUILD.md", "build_script": "build.sh", "latexmkrc": "latexmkrc",
                      "environment": "environment.json", "logs": "build_logs/"},
        "build": {"main": main_rel, "engine": engine, "bibtool": R["bib_ran"] or bibtool, "commands": cmds, "engine_passes": R["engine_passes"], "converged": R["converged"],
                  "timeout": R["timeout"], "seconds": R["seconds"], "rounds": R["rounds"], "source_date_epoch": str(epoch), "reproducibility": repro},
        "diagnostics_summary": {"errors_in_log": len(log_err), "root_causes": [_short(d) for d in roots_[:30]], "errors_total": len(errors),
                                "undefined_references": undef_ref, "undefined_citations": undef_cite, "overfull_boxes": [_short(d) for d in overfull[:20]],
                                "missing_glyphs": sorted({d["char"] for d in glyphs})[:50], "warnings": sum(1 for d in D if d["severity"] == "warning")},
        "requirements": reqs,
        "changes": change_log,
        "change_records": recs,
        "sources": {"input_dir": st.get("input_dir"), "materials": st.get("materials"), "original_snapshot": "work/orig (unchanged input)",
                    "fact_guard": {"numbers_changed_in_edits": [_short(d) for d in audit if d["class"] == "number_changed"],
                                   "keys_changed_in_edits": [_short(d) for d in audit if d["class"] == "key_changed"],
                                   "numbers_not_in_materials": newnums[:50]}},
        "needs_confirmation": nc, "uncertainty": unc, "notes": changes.get("notes") or [],
        "environment": {"distribution": env.get("distribution"), "engine_version": env["engine"]["version"], "bibtool_version": (env.get("bibtool") or {}).get("version"),
                        "documentclass": env.get("documentclass"), "n_packages": len(env.get("packages", {})), "details": "environment.json"},
    }
    fields = st.get("contract_fields") or []
    overrides = changes.get("fields") or {}
    unmapped_fields = []
    for f in fields:
        if f in res and f not in overrides:
            continue
        mapped = map_field(f, res, overrides)
        if isinstance(mapped, dict) and mapped.get("note", "").startswith("no automatic mapping"):
            unmapped_fields.append(f)
        res[f] = mapped
    for f, v in overrides.items():
        if f not in fields:
            res[f] = v.get("value") if isinstance(v, dict) and "value" in v else v
    write_json(os.path.join(out, "result.json"), res)
    write_report(out, res, D, roots_, reqs, change_log, newnums)
    rc = 0 if status == "success" else (1 if R["pdf"] else 2)
    if not a.quiet:
        print_console(res, D, roots_, reqs, audit, newnums, a.max_show, time.time() - t0, unmapped_fields)
    return rc


def link_origins(D):
    """TeX reports unclosed groups/environments where it gives up (end of file, \\end{document}); the static scan knows
    where they were opened. Point the log error to that origin and make the static finding the root."""
    stat = [d for d in D if d.get("source") == "static" and d["severity"] == "error" and d["class"] in ("brace", "env_mismatch", "math_mode")]
    if not stat:
        return
    for d in D:
        if d.get("source") != "log" or d["severity"] != "error" or d.get("cascade_of") or d["class"] not in ("runaway", "no_end", "brace", "env_mismatch", "math_mode"):
            continue
        sl = d.get("source_line") or ""
        target = None
        m = re.search(r"\\(?:input|include|subfile)\s*\{([^}]+)\}", sl)
        if m:
            t = m.group(1).strip()
            target = [s for s in stat if s.get("file") and os.path.splitext(s["file"])[0].endswith(os.path.splitext(t)[0])]
        same = [s for s in stat if s.get("file") == d.get("file") and (s.get("line") or 0) <= (d.get("line") or 10 ** 9)]
        cand = target or same
        if not cand and d["class"] in ("runaway", "no_end"):
            cand = stat
        if cand:
            o = max(cand, key=lambda s: (s.get("file") == d.get("file"), s.get("line") or 0)) if not target else cand[0]
            d["likely_origin"] = "%s:%s" % (o.get("file"), o.get("line"))
            d["cascade_of"] = o["id"]
            d["hint"] = (d.get("hint") or "") + " Opened at %s:%s (%s)." % (o.get("file"), o.get("line"), o["message"][:80])


def _short(d):
    return {k: d.get(k) for k in ("id", "class", "file", "line", "message", "hint", "cascade_of", "key", "cs", "name") if d.get(k) is not None}


def map_field(f, res, overrides):
    if f in overrides:
        v = overrides[f]
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        if isinstance(v, dict) and "from" in v:
            return _get(res, v["from"])
        return v
    k = f.lower()
    if k in ("source", "fixed_source", "tex_source", "fixed_tex", "fixed_project", "deliverable_tex", "output_tex", "latex_source", "main_tex"):
        return res["artifacts"]
    if k in ("unresolved_citations", "undefined_citations", "missing_citations"):
        return res["diagnostics_summary"]["undefined_citations"]
    if k in ("unresolved_references", "undefined_references", "missing_references"):
        return res["diagnostics_summary"]["undefined_references"]
    if k in ("open_questions", "open_items", "questions", "manual_confirmations"):
        return res["needs_confirmation"]
    table = [
        (("status", "state", "outcome"), lambda: res["status"]),
        (("pdf",), lambda: res["artifacts"]["pdf"]),
        (("log",), lambda: res["artifacts"]["logs"]),
        (("diff", "patch"), lambda: res["artifacts"]["diff"]),
        (("unresolved_cit", "undefined_cit", "missing_cit"), lambda: res["diagnostics_summary"]["undefined_citations"]),
        (("unresolved_ref", "undefined_ref", "missing_ref"), lambda: res["diagnostics_summary"]["undefined_references"]),
        (("open_question", "open_item", "confirm", "manual", "human", "review", "todo"), lambda: res["needs_confirmation"]),
        (("change", "modif", "edit", "revision", "bib_fix", "bibliography_fix", "fixes"), lambda: res["changes"]),
        (("diagnos", "error", "issue", "problem", "warning", "remaining"), lambda: res["diagnostics_summary"]),
        (("command", "compile", "build", "reproduc", "recipe", "step"), lambda: res["build"]),
        (("environment", "version", "distribution", "package", "dependenc", "font"), lambda: res["environment"]),
        (("uncertain", "limit", "gap", "risk", "caveat"), lambda: res["uncertainty"]),
        (("source_map", "provenance", "evidence", "fact", "trace", "material"), lambda: res["sources"]),
        (("requirement", "template", "checklist", "compliance"), lambda: res["requirements"]),
        (("tex", "latex", "artifact", "deliverable", "output", "file", "project", "manuscript", "document", "main", "result", "fixed", "source"), lambda: res["artifacts"]),
        (("citation", "reference"), lambda: res["sources"]),
        (("summary", "report", "description", "note", "explanation"), lambda: res["summary"]),
        (("case",), lambda: res["case_id"]),
    ]
    for keys, fn in table:
        if any(x in k for x in keys):
            return fn()
    return {"value": None, "note": "no automatic mapping for this field - set it in work/changes.json fields"}


def _get(obj, path):
    for p in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(p)
        else:
            return None
    return obj


def write_build_files(out, main_rel, engine, bibtool, cmds, epoch, env, R, shell_escape):
    d = os.path.dirname(main_rel) or "."
    job = os.path.splitext(os.path.basename(main_rel))[0]
    sh = ["#!/bin/sh", "# Rebuild exactly as latex-build-doctor did (run from this output directory).", "set -e",
          "export SOURCE_DATE_EPOCH=%s max_print_line=10000" % epoch, "cd \"$(dirname \"$0\")/src/%s\"" % d]
    sh += [c for c in cmds]
    sh += ["echo built: $(pwd)/%s.pdf" % job]
    write_text(os.path.join(out, "build.sh"), "\n".join(sh) + "\n")
    pdf_mode = {"pdflatex": 1, "xelatex": 5, "lualatex": 4, "latex": 3, "platex": 3, "uplatex": 3}[engine]
    rc = ["# latexmkrc generated by latex-build-doctor %s" % VERSION, "$pdf_mode = %d;" % pdf_mode,
          "$%s = '%s -interaction=nonstopmode -file-line-error -recorder %s %%O %%S';" % ({"pdflatex": "pdflatex", "xelatex": "xelatex", "lualatex": "lualatex"}.get(engine, "latex"), engine, "-shell-escape" if shell_escape else "-no-shell-escape"),
          "$bibtex_use = 2;" if bibtool else "$bibtex_use = 0;", "$ENV{'SOURCE_DATE_EPOCH'} = '%s';" % epoch, "$max_repeat = 5;"]
    if bibtool == "biber":
        rc.append("$biber = 'biber %O %S';")
    write_text(os.path.join(out, "latexmkrc"), "\n".join(rc) + "\n")
    pk = env.get("packages", {})
    lines = ["# How to rebuild", "", "Main file: `src/%s` - engine **%s**%s." % (main_rel, engine, (", bibliography with **%s**" % bibtool) if bibtool else ""), "",
             "## Commands (run in `src/%s`, in this order)" % d, "", "```sh", "export SOURCE_DATE_EPOCH=%s   # fixes PDF dates/ID -> byte-identical rebuilds" % epoch, "export max_print_line=10000"]
    lines += cmds + ["```", "", "Equivalent: `cd src/%s && latexmk -r ../%slatexmkrc %s.tex` (or `sh build.sh`)." % (d, "../" * (main_rel.count("/")), job), "",
                     "## Environment recorded at build time", "",
                     "- distribution: %s" % env.get("distribution"), "- engine: %s" % (env["engine"].get("version") or "?"),
                     "- bib tool: %s" % ((env.get("bibtool") or {}).get("version") or "none"),
                     "- document class: %s" % json.dumps(env.get("documentclass"), ensure_ascii=False),
                     "- project files read by TeX: %s" % ", ".join(env.get("project_files_used", [])[:40]),
                     "- PDF fonts: %s" % ", ".join("%s(%s)" % (f["name"], "emb" if f["embedded"] == "yes" else "NOT embedded") for f in env.get("pdf_fonts", [])[:30]), "",
                     "| package | date | version |", "|---|---|---|"]
    for k in sorted(pk):
        lines.append("| %s | %s | %s |" % (k, pk[k]["date"], pk[k]["version"].replace("|", "/")[:60]))
    write_text(os.path.join(out, "BUILD.md"), "\n".join(lines) + "\n")


def write_report(out, res, D, roots_, reqs, change_log, newnums):
    b = res["build"]
    L = ["# Build report (%s)" % res["status"], "", res["summary"], "",
         "- commands: " + " -> ".join("`%s`" % c for c in b["commands"]),
         "- converged: %s; reproducible: %s" % (b["converged"], b["reproducibility"].get("byte_identical", "not checked")),
         "- PDF: %s (%s pages)" % (res["artifacts"]["pdf"], res["artifacts"]["pdf_pages"]), ""]
    if roots_:
        L += ["## Root causes (fix in this order)", "", "| id | class | where | message | hint |", "|---|---|---|---|---|"]
        for d in roots_[:40]:
            casc = sum(1 for x in D if x.get("cascade_of") == d["id"])
            L.append("| %s | %s | %s:%s | %s%s | %s |" % (d["id"], d["class"], d.get("file"), d.get("line"), _md(d["message"])[:160], (" (+%d follow-on)" % casc) if casc else "", _md(d.get("hint", ""))[:200]))
        L.append("")
    W = [d for d in D if d["severity"] == "warning"]
    if W:
        L += ["## Warnings", "", "| id | class | where | message |", "|---|---|---|---|"]
        for d in W[:60]:
            L.append("| %s | %s | %s:%s | %s |" % (d["id"], d["class"], d.get("file"), d.get("line"), _md(d["message"])[:180]))
        L.append("")
    if reqs:
        L += ["## Requirements", "", "| id | ok | requirement | origin |", "|---|---|---|---|"]
        for r in reqs:
            L.append("| %s | %s | %s | %s |" % (r["id"], r["ok"], _md(r["desc"] or ""), r["origin"]))
        L.append("")
    if change_log:
        L += ["## Changes (diff vs original input)", "", "| hunk | file | new lines | documented | reason |", "|---|---|---|---|---|"]
        for c in change_log:
            L.append("| %s | %s | %s-%s | %s | %s |" % (c["hunk"], c["file"], c["new_lines"][0], c["new_lines"][1], c["documented"], _md("; ".join(r or "" for r in c["reasons"]))[:200]))
        L.append("")
    if res["needs_confirmation"]:
        L += ["## Needs human confirmation", ""] + ["- " + _md(json.dumps(x, ensure_ascii=False))[:300] for x in res["needs_confirmation"][:40]] + [""]
    if res["uncertainty"]:
        L += ["## Uncertainty / limits", ""] + ["- " + x for x in res["uncertainty"]] + [""]
    write_text(os.path.join(out, "build_report.md"), "\n".join(L))


def _md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def print_console(res, D, roots_, reqs, audit, newnums, max_show, secs, unmapped_fields=()):
    b = res["build"]
    print("status: %s  (%.1f s)" % (res["status"], secs))
    print(res["summary"])
    print("rounds: " + " -> ".join("%s[%s]" % (r["step"], r["exit"]) for r in b["rounds"]))
    rp = b["reproducibility"]
    if rp.get("checked"):
        print("reproducible (2 clean builds, SOURCE_DATE_EPOCH=%s): %s" % (rp["source_date_epoch"], "byte-identical PDF" if rp["byte_identical"] else "PDF bytes DIFFER"))
    if roots_:
        print("ROOT CAUSES (fix top-down; follow-on errors hidden):")
        for d in roots_[:max_show]:
            casc = sum(1 for x in D if x.get("cascade_of") == d["id"])
            print("  %s %-16s %s:%s  %s%s" % (d["id"], d["class"], d.get("file"), d.get("line"), d["message"][:150], ("  (+%d follow-on)" % casc) if casc else ""))
            if d.get("source_line"):
                print("       src: %s" % d["source_line"][:150])
            if d.get("context"):
                print("       log: %s" % d["context"][:150])
            if d.get("hint"):
                print("       fix: %s" % d["hint"][:300])
        if len(roots_) > max_show:
            print("  ... %d more in diagnostics.json" % (len(roots_) - max_show))
    W = [d for d in D if d["severity"] == "warning"]
    for d in W[:max_show]:
        print("  warn %s %s:%s %s%s" % (d["class"], d.get("file"), d.get("line"), d["message"][:140], (" -> " + d["hint"][:160]) if d.get("hint") else ""))
    if len(W) > max_show:
        print("  ... %d more warnings in diagnostics.json" % (len(W) - max_show))
    for r in reqs:
        if r["ok"] is not True:
            print("  requirement %s %s: %s" % (r["id"], "FAILED" if r["ok"] is False else "unchecked", r["desc"]))
    if newnums:
        print("  fact guard: %d number(s) in the body not found in any input material, e.g. %s" % (len(newnums), ", ".join("%s@%s:%s" % (x["number"], x["file"], x["line"]) for x in newnums[:6])))
    if unmapped_fields:
        print("  WARN unmapped output_contract field(s) in result.json (%s) - populate them via work/changes.json -> fields" % ", ".join(unmapped_fields))
    print("outputs: result.json, build_report.md, diagnostics.json, src/, PDF, preview/, BUILD.md, changes.diff, change_log.json")


if __name__ == "__main__":
    sys.exit(main())
