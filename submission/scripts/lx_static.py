"""Static checks on LaTeX sources and .bib files (no compilation needed). Every finding has file + line."""
import difflib
import os
import re

from lx_common import code_lines, find_commands, find_multi_arg_commands, load_rules, read_text, rel, split_csv

REF_CMDS = ["ref", "eqref", "pageref", "autoref", "cref", "Cref", "vref", "nameref", "labelcref", "cpageref", "Cpageref", "subref", "crefrange", "Crefrange"]
CITE_CMDS = ["cite", "citep", "citet", "citealp", "citealt", "citeauthor", "citeyear", "citeyearpar", "parencite", "textcite", "autocite", "footcite",
             "supercite", "smartcite", "nocite", "Cite", "Citep", "Citet", "Parencite", "Textcite", "Autocite", "fullcite", "citenum", "citeonline", "upcite"]
PLURAL_CITE_CMDS = ["cites", "parencites", "textcites", "autocites", "footcites", "supercites", "fullcites", "Cites", "Parencites", "Textcites", "Autocites"]
REQUIRED_BIB = {
    "article": ["author", "title", "journal|journaltitle", "year|date"],
    "book": ["author|editor", "title", "publisher", "year|date"],
    "inproceedings": ["author", "title", "booktitle", "year|date"],
    "conference": ["author", "title", "booktitle", "year|date"],
    "incollection": ["author", "title", "booktitle", "publisher", "year|date"],
    "phdthesis": ["author", "title", "school|institution", "year|date"],
    "mastersthesis": ["author", "title", "school|institution", "year|date"],
    "thesis": ["author", "title", "institution|school", "year|date"],
    "techreport": ["author", "title", "institution", "year|date"],
    "misc": [], "online": ["title", "url|doi"], "unpublished": ["author", "title"],
}
UNIT = r"(?:nm|mm|cm|km|µm|um|kg|mg|g|ms|ns|ps|Hz|kHz|MHz|GHz|eV|meV|keV|MeV|K|mol|mM|mL|ml|L|V|mV|kV|W|mW|kW|Pa|kPa|MPa|GPa|min|h|dB|wt|rpm|T|mT|A|mA|J|kJ|N|C)"
UNIT_IN_MATH = re.compile(r"\$\s*-?\d+(?:\.\d+)?\s*(?:\\[,;:!]|~|\\ )?\s*" + UNIT + r"(?:\^\{?-?\d\}?)?\s*\$")
WORD_SUB = re.compile(r"(?<![\\A-Za-z])([A-Za-z])_\{?([A-Za-z]{3,})\}?")
TEXT_SUBS = {"max", "min", "eff", "tot", "total", "opt", "ref", "avg", "mean", "train", "test", "init", "true", "pred", "out", "in", "obs", "sat", "crit", "loss", "rms", "std"}


def scan_project(src_root, files, main_rel, engine):
    """files: list of project-relative .tex paths reached from the main file (or all). Returns findings list."""
    rules = load_rules("packages.json")
    F = []
    labels, refs, cites, bibkeys = {}, [], [], {}
    pkgs = []
    newcmds = set()

    def add(cls, sev, f, line, msg, hint=None, **kw):
        d = {"class": cls, "severity": sev, "file": f, "line": line, "message": msg, "source": "static"}
        if hint:
            d["hint"] = hint
        d.update(kw)
        F.append(d)

    texts = {}
    for f in files:
        p = os.path.join(src_root, f)
        if not os.path.isfile(p):
            continue
        text, enc = read_text(p)
        lines = code_lines(text)
        texts[f] = (text, lines)
        code = "\n".join(lines)
        brace_env_check(f, lines, add)
        for _, _, a, ln, _ in find_commands(code, ["label"]):
            if a:
                labels.setdefault(a.strip(), []).append((f, ln))
        for c, _, a, ln, _ in find_commands(code, REF_CMDS):
            for k in split_csv(a):
                refs.append((k, f, ln, c))
        for c, _, a, ln, _ in find_commands(code, CITE_CMDS):
            for k in split_csv(a):
                if k != "*":
                    cites.append((k, f, ln, c))
        for c, a, ln in find_multi_arg_commands(code, PLURAL_CITE_CMDS):
            for k in split_csv(a):
                if k != "*":
                    cites.append((k, f, ln, c))
        for _, _, a, ln, _ in find_commands(code, ["newcommand", "renewcommand", "providecommand", "DeclareMathOperator", "def", "NewDocumentCommand", "DeclareRobustCommand", "let"]):
            if a:
                newcmds.add(a.strip().lstrip("\\"))
        for m in re.finditer(r"\\(?:def|let)\s*\\([A-Za-z@]+)", code):
            newcmds.add(m.group(1))
        for name, opt, arg, ln, pos in find_commands(code, ["usepackage", "RequirePackage"]):
            for pk in split_csv(arg):
                pkgs.append({"name": pk, "options": split_csv(opt), "file": f, "line": ln})
        float_checks(f, lines, add)
        table_checks(f, lines, add)
        style_checks(f, lines, add, engine)
    # labels / refs
    for k, locs in labels.items():
        if len(locs) > 1:
            add("duplicate_label", "error", locs[1][0], locs[1][1], "label '%s' defined %d times (first at %s:%d)" % (k, len(locs), locs[0][0], locs[0][1]),
                "Every \\label must be unique; rename one and update its \\ref.", key=k)
    for k, f, ln, c in refs:
        if k not in labels and not k.startswith("#"):
            sug = difflib.get_close_matches(k, list(labels), n=2, cutoff=0.6)
            add("undefined_ref", "error", f, ln, "\\%s{%s}: no \\label{%s} in the project" % (c, k, k),
                ("closest existing labels: " + ", ".join(sug) + " - fix the key, do not invent a target.") if sug else "No matching label: replace \\%s{%s} with a clear text placeholder + %% TODO(author) and record in needs_confirmation so PDF does not show '??'." % (c, k),
                key=k, suggestions=sug)
    return F, {"labels": labels, "refs": refs, "cites": cites, "packages": pkgs, "newcommands": newcmds, "texts": texts}


def brace_env_check(f, lines, add):
    depth_stack = []  # (line, col)
    env_stack = []
    math_open = None
    for ln, line in enumerate(lines, 1):
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\":
                m = re.match(r"\\(begin|end)\s*\{([^}]*)\}", line[i:])
                if m:
                    env = m.group(2).strip()
                    if m.group(1) == "begin":
                        env_stack.append((env, ln))
                    else:
                        if env_stack and env_stack[-1][0] == env:
                            env_stack.pop()
                        elif env_stack and any(e == env for e, _ in env_stack):
                            while env_stack and env_stack[-1][0] != env:
                                e, l0 = env_stack.pop()
                                add("env_mismatch", "error", f, l0, "\\begin{%s} (line %d) is never closed before \\end{%s} at line %d" % (e, l0, env, ln),
                                    "Insert \\end{%s} where the environment should end (before line %d)." % (e, ln), env=e, closing_line=ln)
                            env_stack.pop()
                        elif env_stack and env_stack[-1][0] != "document":
                            e, l0 = env_stack.pop()
                            add("env_mismatch", "error", f, ln, "\\begin{%s} (line %d) is closed by \\end{%s}" % (e, l0, env),
                                "Use \\end{%s} here (or \\begin{%s} at line %d) - pick the one the content intends." % (e, env, l0), env=e, opened_line=l0)
                        elif env != "document" or env_stack:
                            add("env_mismatch", "error", f, ln, "\\end{%s} without matching \\begin{%s}" % (env, env), "Remove it or add the missing \\begin.", env=env)
                    i += m.end()
                    continue
                if line[i : i + 2] in ("\\[", "\\]"):
                    if line[i + 1] == "[":
                        if math_open:
                            add("math_mode", "error", f, ln, "\\[ opened at line %d is not closed before a new \\[" % math_open[1], "Close display math with \\].")
                        math_open = ("\\[", ln)
                    else:
                        math_open = None
                i += 2
                continue
            if ch == "{":
                depth_stack.append((ln, i))
            elif ch == "}":
                if depth_stack:
                    depth_stack.pop()
                else:
                    add("brace", "error", f, ln, "unmatched '}' at line %d col %d" % (ln, i + 1), "Delete the extra '}' or add the missing '{'.", col=i + 1)
            i += 1
        if line.strip() == "" and math_open:
            add("math_mode", "error", f, ln, "blank line inside display math opened at line %d" % math_open[1], "Remove the blank line (paragraph breaks are not allowed in math).")
            math_open = None
    for (l0, c0) in depth_stack[:3]:
        add("brace", "error", f, l0, "'{' at line %d col %d is never closed in this file" % (l0, c0 + 1),
            "Add the missing '}' (the compiler usually reports this much later, e.g. 'File ended' / 'Runaway argument').", col=c0 + 1)
    if f and env_stack:
        for e, l0 in env_stack:
            if e != "document":
                add("env_mismatch", "error", f, l0, "\\begin{%s} at line %d is never closed in this file" % (e, l0), "Add \\end{%s}." % e, env=e)


def float_checks(f, lines, add):
    code = "\n".join(lines)
    for m in re.finditer(r"\\begin\{(figure|table|figure\*|table\*|subfigure|subtable|algorithm|wrapfigure|wraptable|sidewaystable|sidewaysfigure)\}(.*?)\\end\{\1\}", code, re.S):
        body = m.group(2)
        l0 = code.count("\n", 0, m.start()) + 1
        cap = body.find("\\caption")
        for lm in re.finditer(r"\\label\{([^}]*)\}", body):
            if cap < 0:
                add("float_label", "warning", f, l0 + body.count("\n", 0, lm.start()), "\\label{%s} in a %s without \\caption: \\ref will print the section number" % (lm.group(1), m.group(1)),
                    "Add a \\caption before the \\label.", key=lm.group(1))
            elif lm.start() < cap and not body[:lm.start()].count("\\caption"):
                add("float_label", "error", f, l0 + body.count("\n", 0, lm.start()), "\\label{%s} comes before \\caption in this %s: \\ref gives the wrong (section) number" % (lm.group(1), m.group(1)),
                    "Move \\label after (or inside) \\caption.", key=lm.group(1))
        opt = re.match(r"\s*\[([^\]]*)\]", body)
        if opt and opt.group(1).strip() in ("h", "H!") and m.group(1) in ("figure", "table"):
            add("float_spec", "info", f, l0, "float placement [%s] only - LaTeX will change it to [ht]" % opt.group(1), "Use [htbp] (or [tbp]) unless the template says otherwise.")
        if re.search(r"\\(resizebox|scalebox)\s*\{[^}]*\}\s*(\{[^}]*\}\s*)?\{\s*\\begin\{tabular", body) or re.search(r"\\(resizebox|scalebox)[^\n]*\n?\s*\\begin\{tabular", body):
            add("table_scaled", "warning", f, l0, "tabular wrapped in \\resizebox/\\scalebox: font size changes with the content and can fall below the template minimum",
                "Fit the table instead: tabularx / p{...} columns, \\small or \\footnotesize, abbreviations in the header, table* or landscape for very wide tables.")


def column_count(spec):
    s = re.sub(r"\s", "", spec)
    n, i = 0, 0
    while i < len(s):
        ch = s[i]
        if ch == "*":
            a, j = _grp(s, i + 1)
            b, k = _grp(s, j)
            try:
                n += int(a) * column_count(b)
            except (TypeError, ValueError):
                return None
            i = k
            continue
        if ch in "@!><":
            _, j = _grp(s, i + 1)
            i = j
            continue
        if ch in "pmbwWQ":
            _, j = _grp(s, i + 1)
            if ch in "wW":
                _, j = _grp(s, j)
            n += 1
            i = j
            continue
        if ch in "S":
            n += 1
            i += 1
            if i < len(s) and s[i] == "[":
                j = s.find("]", i)
                i = j + 1 if j > 0 else i + 1
            continue
        if ch in "lcrXLCRJYZs":
            n += 1
        i += 1
    return n


def _grp(s, i):
    if i < len(s) and s[i] == "{":
        d = 0
        for j in range(i, len(s)):
            if s[j] == "{":
                d += 1
            elif s[j] == "}":
                d -= 1
                if d == 0:
                    return s[i + 1 : j], j + 1
    return None, i + 1


def _find_matching_end(code, env, start):
    pat = re.compile(r"\\(begin|end)\s*\{" + re.escape(env) + r"\}")
    depth = 1
    for m in pat.finditer(code, start):
        depth += 1 if m.group(1) == "begin" else -1
        if depth == 0:
            return m.start()
    return -1


_INNER_ALIGN_ENVS = re.compile(
    r"\\begin\{(pmatrix|bmatrix|vmatrix|Bmatrix|Vmatrix|matrix|smallmatrix|cases|dcases|rcases|aligned|gathered|split|array|tabular\*?|tabularx)\}.*?\\end\{\1\}",
    re.S,
)


def _blank_inner_envs(body):
    # Preserve newlines so line-number computation remains exact while ignoring inner & and \\.
    prev = None
    cur = body
    while cur != prev:
        prev = cur
        cur = _INNER_ALIGN_ENVS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), cur)
    return cur


def table_checks(f, lines, add):
    code = "\n".join(lines)
    for m in re.finditer(r"\\begin\{(tabular\*?|tabularx|longtable|tabulary|xltabular|array)\}", code):
        i = m.end()
        env = m.group(1)
        if env in ("tabular*", "tabularx", "tabulary", "xltabular"):
            _, i = _skip_arg(code, i)
        if i < len(code) and code[i] == "[" and env != "longtable":
            j = code.find("]", i)
            i = j + 1
        while i < len(code) and code[i] in " \n":
            i += 1
        if i < len(code) and code[i] == "[":
            j = code.find("]", i)
            i = j + 1
        spec, j = _grp(code, i)
        if spec is None:
            continue
        ncol = column_count(spec)
        end = _find_matching_end(code, env, j)
        if end < 0 or not ncol:
            continue
        body = _blank_inner_envs(code[j:end])
        l0 = code.count("\n", 0, j) + 1
        body = re.sub(r"\\\\(\[[^\]]*\])?", "\\\\\\\\", body)
        pos = 0
        over, short = [], []
        for row in re.split(r"\\\\", body):
            amp = row.find("&")
            rl = l0 + body.count("\n", 0, pos) + (row[:amp].count("\n") if amp >= 0 else row.count("\n", 0, len(row) - len(row.lstrip())))
            pos += len(row) + 2
            r = re.sub(r"\\(hline|toprule|midrule|bottomrule|endhead|endfirsthead|endfoot|endlastfoot|cline\{[^}]*\}|cmidrule(\([^)]*\))?\{[^}]*\}|addlinespace(\[[^\]]*\])?|rowcolor(\[[^\]]*\])?\{[^}]*\}|noalign\{[^}]*\})", "", row)
            r = _strip_groups(r)
            if not r.strip():
                continue
            cells = 1 + len(re.findall(r"(?<!\\)&", r))
            for mc in re.finditer(r"\\multicolumn\s*\{\s*(\d+)\s*\}", row):
                cells += int(mc.group(1)) - 1
            if cells > ncol:
                over.append((rl, cells))
            elif cells < ncol and "\\multicolumn" not in row and cells > 1 and not re.search(r"\\(caption|label)", row):
                short.append((rl, cells))
        if over:
            add("table_columns", "error", f, over[0][0], "%d row(s) have more cells than the %s spec '{%s}' (%d columns): lines %s (cells %s)" % (
                len(over), env, spec, ncol, ",".join(str(x[0]) for x in over), ",".join(str(x[1]) for x in over)),
                "Compare against the source data. Extend the column spec when values need more columns, or escape literal ampersands as \\&. Preserve each value and its math or references.",
                cells=[x[1] for x in over], columns=ncol, rows=[x[0] for x in over], table_line=l0)
        if short:
            add("table_columns", "info", f, short[0][0], "%d short row(s) (fewer cells than %d columns): lines %s" % (len(short), ncol, ",".join(str(x[0]) for x in short)),
                "Fine if intentional; otherwise a value is missing.", columns=ncol, rows=[x[0] for x in short])


def _skip_arg(code, i):
    while i < len(code) and code[i] in " \n":
        i += 1
    a, j = _grp(code, i)
    return a, j


def _strip_groups(s):
    out, d = [], 0
    for ch in s:
        if ch == "{":
            d += 1
            continue
        if ch == "}":
            d = max(0, d - 1)
            continue
        if d == 0 or ch != "&":
            out.append(ch if d == 0 else (" " if ch == "&" else ch))
    return "".join(out)


def style_checks(f, lines, add, engine):
    cjk = []
    for ln, line in enumerate(lines, 1):
        if re.search(r"(?<!\\)\$\$", line):
            add("display_math", "info", f, ln, "$$...$$ display math (plain TeX) - wrong spacing, breaks fleqn", "Use \\[ ... \\] or equation*.")
        if "\\begin{eqnarray" in line:
            add("display_math", "info", f, ln, "eqnarray has inconsistent spacing", "Use align (amsmath); keep the labels.")
        for m in UNIT_IN_MATH.finditer(line):
            add("unit_italic", "warning", f, ln, "unit set in math italic: %s" % m.group(0), "Write the unit upright: \\SI{..}{..}/\\qty (siunitx) or 5~\\mathrm{nm} - keep the number unchanged.")
        for m in WORD_SUB.finditer(line):
            if m.group(2).lower() in TEXT_SUBS and "$" in line:
                add("subscript_italic", "info", f, ln, "descriptive subscript in italic: %s_%s" % (m.group(1), m.group(2)), "Use %s_{\\mathrm{%s}} (or \\max/\\min operators)." % (m.group(1), m.group(2)))
        if re.search(r"\\\\\s*$", line) and ln < len(lines) and lines[ln].strip() == "" and not re.search(r"&|\\(item|hline|midrule|toprule|bottomrule)", line):
            add("bad_linebreak", "warning", f, ln, "\\\\ before a blank line ('There's no line here to end' / Underfull hbox)", "Remove the \\\\; a blank line already ends the paragraph.")
        if engine == "pdflatex" and re.search(r"[\u4e00-\u9fff]", line):
            cjk.append(ln)
    if cjk:
        add("cjk_pdflatex", "warning", f, cjk[0], "CJK text under pdfLaTeX on %d line(s): %s" % (len(cjk), ",".join(map(str, cjk[:12]))),
            "Use ctex/xeCJK with XeLaTeX (or CJKutf8 under pdfLaTeX); otherwise characters are lost.", rows=cjk)


def package_checks(pkgs, engine, cls_name):
    rules = load_rules("packages.json")
    F = []
    names = [p["name"] for p in pkgs]
    first = {}
    for k, p in enumerate(pkgs):
        first.setdefault(p["name"], (k, p))
    for c in rules["conflicts"]:
        sev = c.get("severity", "warning")
        if c["a"] == c["b"]:
            if names.count(c["a"]) > 1:
                p = [x for x in pkgs if x["name"] == c["a"]][1]
                F.append({"class": "package_conflict", "severity": sev, "file": p["file"], "line": p["line"], "message": "%s loaded more than once" % c["a"], "hint": c["why"], "source": "static"})
        elif c["a"] in first and c["b"] in first:
            p = first[c["a"]][1]
            F.append({"class": "package_conflict", "severity": sev, "file": p["file"], "line": p["line"], "message": "%s together with %s" % (c["a"], c["b"]), "hint": c["why"], "source": "static"})
    for lo in rules["load_order"]:
        if lo["pkg"] not in first:
            continue
        k, p = first[lo["pkg"]]
        if "engine" in lo and engine not in lo["engine"]:
            F.append({"class": "engine_mismatch", "severity": "error", "file": p["file"], "line": p["line"], "message": "%s with engine %s" % (lo["pkg"], engine), "hint": lo["why"], "source": "static"})
        if "must_be_after" in lo:
            if lo["must_be_after"] == ["*"]:
                later = [x for x in pkgs[k + 1 :] if x["name"] not in lo.get("except", []) and x["name"] != lo["pkg"] and x["file"] == p["file"]]
                if later:
                    F.append({"class": "load_order", "severity": "warning", "file": later[0]["file"], "line": later[0]["line"],
                              "message": "%s loaded after hyperref (line %d)" % (", ".join(x["name"] for x in later[:4]), p["line"]), "hint": lo["why"], "source": "static"})
            else:
                for b in lo["must_be_after"]:
                    if b in first and first[b][0] > k:
                        F.append({"class": "load_order", "severity": "warning", "file": p["file"], "line": p["line"], "message": "%s is loaded before %s" % (lo["pkg"], b), "hint": lo["why"], "source": "static"})
        if "options_needed_before" in lo:
            for b in lo["options_needed_before"]:
                later_x = [x for x in pkgs if x["name"] == lo["pkg"] and x["options"]]
                if b in first and later_x and first[b][0] < pkgs.index(later_x[0]):
                    F.append({"class": "load_order", "severity": "warning", "file": later_x[0]["file"], "line": later_x[0]["line"],
                              "message": "xcolor with options [%s] loaded after %s" % (",".join(later_x[0]["options"]), b), "hint": lo["why"], "source": "static"})
    for obs, repl in (("subfigure", "subcaption"), ("epsfig", "graphicx"), ("times", "newtxtext,newtxmath or mathptmx"), ("a4wide", "geometry"),
                      ("doublespace", "setspace"), ("caption2", "caption"), ("t1enc", "fontenc[T1]"), ("isolatin1", "inputenc"), ("psfig", "graphicx"), ("fixltx2e", "(not needed since 2015)")):
        if obs in first:
            p = first[obs][1]
            F.append({"class": "obsolete_package", "severity": "info", "file": p["file"], "line": p["line"], "message": "obsolete package %s" % obs, "hint": "Prefer " + repl, "source": "static"})
    return F


# ---------------------------------------------------------------- bib


def parse_bib(path, relpath):
    raw, enc = read_text(path)
    # Blank comment-only lines (preserving line numbers) so commented @entries are ignored.
    text = "\n".join("" if re.match(r"^\s*%", ln) else ln for ln in raw.split("\n"))
    entries, F = {}, []
    for m in re.finditer(r"@(\w+)\s*([{(])", text):
        typ = m.group(1).lower()
        ln = text.count("\n", 0, m.start()) + 1
        if typ in ("comment", "preamble", "string"):
            continue
        open_c = m.group(2)
        close_c = "}" if open_c == "{" else ")"
        d, j = 0, m.end() - 1
        end = None
        while j < len(text):
            ch = text[j]
            if ch == "\\":
                j += 2
                continue
            if ch == open_c:
                d += 1
            elif ch == close_c:
                d -= 1
                if d == 0:
                    end = j
                    break
            elif ch == "@" and d == 1 and re.match(r"@\w+\s*[{(]", text[j:]) and text[j - 1] == "\n":
                break
            j += 1
        body = text[m.end() : end if end else j]
        km = re.match(r"\s*([^,\s]+)\s*,", body)
        if not km:
            F.append({"class": "bib_syntax", "severity": "error", "file": relpath, "line": ln, "message": "@%s entry without a key/comma" % typ, "hint": "Write @type{key, field = {...}, ...}.", "source": "static"})
            continue
        key = km.group(1)
        if end is None:
            F.append({"class": "bib_syntax", "severity": "error", "file": relpath, "line": ln, "message": "entry %s: braces not balanced (entry never closed)" % key,
                      "hint": "Add the missing '}' - BibTeX will skip this and possibly the following entries.", "key": key, "source": "static"})
        fields = {}
        body_start = m.end() + km.end()
        rest = body[km.end():]
        for fname, problem, off in bib_fields(rest):
            if fname:
                fields[fname.lower()] = True
            if problem:
                pl = text.count("\n", 0, body_start + off) + 1
                F.append({"class": "bib_syntax", "severity": "error", "file": relpath, "line": pl, "message": "entry %s: %s" % (key, problem),
                          "hint": "Fix the field syntax (name = {value}, ...) - BibTeX/biber drop the rest of this entry or the file.", "key": key, "source": "static"})
                break
        if key in entries or key.lower() in {k.lower() for k in entries}:
            F.append({"class": "bib_duplicate", "severity": "error", "file": relpath, "line": ln, "message": "duplicate key %s" % key, "hint": "Merge or rename duplicates.", "key": key, "source": "static"})
        entries[key] = {"type": typ, "line": ln, "fields": list(fields), "file": relpath}
        for req in REQUIRED_BIB.get(typ, []):
            if not any(a in fields for a in req.split("|")):
                F.append({"class": "bib_field", "severity": "warning", "file": relpath, "line": ln, "message": "@%s{%s} has no %s" % (typ, key, req.replace("|", "/")),
                          "hint": "Fill from the source material; if the source does not give it, list it under needs_confirmation (do not invent).", "key": key, "field": req, "source": "static"})
    return entries, F


def bib_fields(s):
    """Yield (field_name, problem, offset) walking 'name = value, name = value' (value: {..}, ".." or bare, joined by #)."""
    i, n = 0, len(s)
    while True:
        while i < n and s[i] in " \t\r\n,":
            i += 1
        if i >= n:
            return
        m = re.match(r"([A-Za-z][\w:.+-]*)\s*=\s*", s[i:])
        if not m:
            yield None, "expected 'field = value' near %r" % s[i:i + 25].strip(), i
            return
        name = m.group(1)
        i += m.end()
        while True:
            if i < n and s[i] == "{":
                d = 0
                j = i
                while j < n:
                    if s[j] == "\\":
                        j += 2
                        continue
                    if s[j] == "{":
                        d += 1
                    elif s[j] == "}":
                        d -= 1
                        if d == 0:
                            break
                    j += 1
                if j >= n:
                    yield name, "value of '%s' has an unclosed '{'" % name, i
                    return
                i = j + 1
            elif i < n and s[i] == '"':
                j = i + 1
                d = 0
                while j < n and not (s[j] == '"' and d == 0):
                    if s[j] == "\\":
                        j += 2
                        continue
                    d += (s[j] == "{") - (s[j] == "}")
                    j += 1
                if j >= n:
                    yield name, "value of '%s' has an unclosed quote" % name, i
                    return
                i = j + 1
            else:
                m2 = re.match(r"[\w.:+-]+", s[i:])
                if not m2:
                    yield name, "field '%s' has no value" % name, i
                    return
                i += m2.end()
            k = i
            while k < n and s[k] in " \t\r\n":
                k += 1
            if k < n and s[k] == "#":
                i = k + 1
                while i < n and s[i] in " \t\r\n":
                    i += 1
                continue
            break
        yield name, None, i
        while i < n and s[i] in " \t\r\n":
            i += 1
        if i < n and s[i] != ",":
            yield None, "missing ',' after field '%s'" % name, i
            return


def cite_checks(cites, bibentries, has_thebib_keys, bibtool=None):
    F = []
    keys = set(bibentries) | set(has_thebib_keys)
    lower = {k.lower(): k for k in keys}
    used = set()
    for k, f, ln, c in cites:
        used.add(k)
        if k in keys:
            continue
        if k.lower() in lower:
            if bibtool == "biber":
                F.append({"class": "undefined_cite", "severity": "warning", "file": f, "line": ln, "message": "\\%s{%s}: key differs only in case from %s (biber is case-sensitive)" % (c, k, lower[k.lower()]),
                          "hint": "Biber keys are case-sensitive: check whether %s is intended." % lower[k.lower()], "key": k, "suggestions": [lower[k.lower()]], "source": "static"})
            else:
                F.append({"class": "undefined_cite", "severity": "info", "file": f, "line": ln, "message": "\\%s{%s}: key differs in case from %s (BibTeX is case-insensitive)" % (c, k, lower[k.lower()]),
                          "hint": "BibTeX is case-insensitive; do not modify the author's \\cite key.", "key": k, "source": "static"})
            continue
        sug = difflib.get_close_matches(k, list(keys), n=2, cutoff=0.7)
        F.append({"class": "undefined_cite", "severity": "error", "file": f, "line": ln, "message": "\\%s{%s}: no entry with this key in the bibliography" % (c, k),
                  "hint": ("closest keys: " + ", ".join(sug) + " - confirm it is the same work before changing the key.") if sug else "The reference is missing from the .bib: add it only from the source material, else mark for human confirmation.",
                  "key": k, "suggestions": sug, "source": "static"})
    for k, e in bibentries.items():
        if k not in used and "*" not in [c[0] for c in cites]:
            F.append({"class": "unused_bib", "severity": "info", "file": e["file"], "line": e["line"], "message": "bib entry %s is never cited" % k, "key": k, "source": "static"})
    return F
