"""Shared helpers for the latex-build-doctor Skill (Python 3.8+, standard library only)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

VERSION = "0.2.0"
HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(os.path.dirname(HERE), "rules")
TEX_EXT = (".tex", ".ltx", ".latex")
SRC_EXT = TEX_EXT + (".bib", ".cls", ".sty", ".bst", ".bbx", ".cbx", ".def", ".cfg", ".clo", ".fd", ".dtx", ".ins", ".tikz", ".pgf")
GRAPHIC_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ps", ".svg", ".jbig2", ".jb2", ".bmp", ".tif", ".tiff", ".gif")
SKIP_DIRS = {".git", "__pycache__", ".svn", "node_modules", "_build_lbd"}
AUX_EXT = (".aux", ".log", ".out", ".toc", ".lof", ".lot", ".bbl", ".blg", ".bcf", ".run.xml", ".fls", ".fdb_latexmk",
           ".synctex.gz", ".nav", ".snm", ".vrb", ".idx", ".ind", ".ilg", ".glo", ".gls", ".glg", ".xdv", ".brf", ".thm")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_rules(name):
    with open(os.path.join(RULES, name), encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_text(path):
    """Return (text, encoding). Tries UTF-8, UTF-8 with BOM, GB18030, CP1252/Latin-1."""
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8", "gb18030", "cp1252", "latin-1"):
        try:
            t = raw.decode(enc)
            if enc == "utf-8" and t.startswith("\ufeff"):
                return t[1:], "utf-8-sig"
            return t, enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8-replace"


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def rel(p, root):
    try:
        return os.path.relpath(p, root).replace(os.sep, "/")
    except ValueError:
        return p.replace(os.sep, "/")


_COMMENT = re.compile(r"(?<!\\)((?:\\\\)*)%.*")
_URL_PROTO = re.compile(r"\\(?:url|path|nolinkurl|href)\s*\{")


def strip_comment(line):
    """Remove a LaTeX comment from one line (keeps \\% and % inside \\url/\\path/\\href)."""
    if "%" not in line:
        return line
    # Mask % inside \url{...}, \path{...}, \nolinkurl{...}, \href{...} so URL percent-encoding is not treated as a comment.
    spans = []
    for m in _URL_PROTO.finditer(line):
        _, end = read_group(line, m.end() - 1)
        if end > m.end() - 1:
            spans.append((m.end() - 1, end))
    if not spans:
        return _COMMENT.sub(r"\1", line)
    for m in _COMMENT.finditer(line):
        pos = m.start() + len(m.group(1))
        if not any(a <= pos < b for a, b in spans):
            return line[:pos]
    return line


VERB_ENVS = ("verbatim", "verbatim*", "lstlisting", "minted", "Verbatim", "comment", "filecontents", "filecontents*")
_VERB_BEGIN = re.compile(r"\\begin\{(" + "|".join(re.escape(e) for e in VERB_ENVS) + r")\}")


def code_lines(text):
    """Lines with comments removed and verbatim bodies blanked (line numbers preserved)."""
    out, in_verb = [], None
    for line in text.split("\n"):
        if in_verb:
            if ("\\end{%s}" % in_verb) in line:
                in_verb = None
                out.append(line[line.index("\\end{") :])
            else:
                out.append("")
            continue
        c = strip_comment(line)
        c = re.sub(r"\\verb\*?(.)(.*?)\1", "\\\\verb||", c)
        c = re.sub(r"\\lstinline(\[[^\]]*\])?(.)(.*?)\2", "\\\\lstinline||", c)
        m = _VERB_BEGIN.search(c)
        if m and ("\\end{%s}" % m.group(1)) not in c[m.end():]:
            in_verb = m.group(1)
            c = c[: m.end()]
        out.append(c)
    return out


def iter_files(root):
    for r, ds, fs in os.walk(root):
        ds[:] = sorted(d for d in ds if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(fs):
            yield os.path.join(r, f)


# ---------------------------------------------------------------- arguments


def read_group(s, i, open_c="{", close_c="}"):
    """s[i] must be open_c; return (content, index_after) honoring nesting and escapes; (None, i) if unbalanced."""
    if i >= len(s) or s[i] != open_c:
        return None, i
    depth, j = 0, i
    while j < len(s):
        ch = s[j]
        if ch == "\\":
            j += 2
            continue
        if ch == open_c:
            depth += 1
        elif ch == close_c:
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    return None, i


def skip_ws(s, i):
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def find_commands(text, names):
    """Yield (name, opt, arg, line_no, start) for \\name[opt]...[opt2]{arg} on comment-free text (multi-line args ok)."""
    pat = re.compile(r"\\(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z@])\*?")
    for m in pat.finditer(text):
        i = skip_ws(text, m.end())
        opt = None
        while i < len(text) and text[i] == "[":
            o, i2 = read_group(text, i, "[", "]")
            if o is None:
                break
            opt = o if opt is None else (opt + "][" + o)
            i = skip_ws(text, i2)
        arg, i3 = read_group(text, i)
        yield m.group(1), opt, arg, text.count("\n", 0, m.start()) + 1, m.start()


def find_multi_arg_commands(text, names):
    """Yield (name, arg, line_no) for commands like \\cites{a}{b} or \\parencites[opt]{a}{b}."""
    pat = re.compile(r"\\(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z@])\*?")
    for m in pat.finditer(text):
        ln = text.count("\n", 0, m.start()) + 1
        i = skip_ws(text, m.end())
        found_any = False
        while i < len(text):
            while i < len(text) and text[i] in "([":
                open_c, close_c = text[i], (")" if text[i] == "(" else "]")
                _, i2 = read_group(text, i, open_c, close_c)
                if i2 == i:
                    break
                i = skip_ws(text, i2)
            if i < len(text) and text[i] == "{":
                arg, i3 = read_group(text, i)
                if arg is None:
                    break
                found_any = True
                yield m.group(1), arg, ln
                i = skip_ws(text, i3)
            else:
                break
        if not found_any:
            continue


def split_csv(arg):
    return [a.strip() for a in (arg or "").split(",") if a.strip()]


# ---------------------------------------------------------------- project scan


def parse_tex_file(path, root):
    text, enc = read_text(path)
    lines = code_lines(text)
    code = "\n".join(lines)
    info = {"path": rel(path, root), "encoding": enc, "n_lines": text.count("\n") + 1, "magic": {}}
    for m in re.finditer(r"^\s*%\s*!\s*TeX\s+(root|program|TS-program|encoding|spellcheck)\s*=\s*(\S+)", text, re.I | re.M):
        info["magic"][m.group(1).lower().replace("ts-", "")] = m.group(2)
    dc = list(find_commands(code, ["documentclass"]))
    info["documentclass"] = None
    if dc:
        _, opt, arg, ln, _ = dc[0]
        info["documentclass"] = {"name": (arg or "").strip(), "options": split_csv(opt), "line": ln}
    bd = re.search(r"\\begin\s*\{document\}", code)
    info["begin_document_line"] = code.count("\n", 0, bd.start()) + 1 if bd else None
    info["has_end_document"] = bool(re.search(r"\\end\s*\{document\}", code))
    pre_end = bd.start() if bd else len(code)
    pk = []
    for name, opt, arg, ln, pos in find_commands(code, ["usepackage", "RequirePackage"]):
        for p in split_csv(arg):
            pk.append({"name": p, "options": split_csv(opt), "line": ln, "in_preamble": pos < pre_end})
    info["packages"] = pk
    inc = []
    for name, opt, arg, ln, pos in find_commands(code, ["input", "include", "subfile", "includeonly", "InputIfFileExists"]):
        if name == "includeonly" or arg is None:
            continue
        inc.append({"cmd": name, "target": arg.strip(), "line": ln})
    for name, opt, arg, ln, pos in find_commands(code, ["import", "subimport", "inputfrom", "subinputfrom"]):
        rest = code[pos:]
        m = re.match(r"\\\w+\*?\s*\{([^}]*)\}\s*\{([^}]*)\}", rest)
        if m:
            inc.append({"cmd": name, "target": (m.group(1).strip().rstrip("/") + "/" + m.group(2).strip()).lstrip("/"), "line": ln})
    info["includes"] = inc
    info["graphics"] = [{"target": a.strip(), "line": ln} for _, _, a, ln, _ in find_commands(code, ["includegraphics"]) if a]
    gp = []
    for _, _, a, ln, _ in find_commands(code, ["graphicspath"]):
        gp += re.findall(r"\{([^{}]*)\}", a or "")
    info["graphicspath"] = gp
    bibs = []
    for name, opt, arg, ln, pos in find_commands(code, ["bibliography", "addbibresource", "addglobalbib"]):
        for b in split_csv(arg):
            bibs.append({"cmd": name, "target": b, "line": ln})
    info["bibs"] = bibs
    info["bibstyle"] = [{"style": (a or "").strip(), "line": ln} for _, _, a, ln, _ in find_commands(code, ["bibliographystyle"])]
    info["has_printbibliography"] = "\\printbibliography" in code
    info["has_thebibliography"] = "\\begin{thebibliography}" in code
    info["fonts"] = [{"cmd": n, "font": (a or "").strip(), "line": ln} for n, _, a, ln, _ in
                     find_commands(code, ["setmainfont", "setsansfont", "setmonofont", "newfontfamily", "setCJKmainfont", "setCJKsansfont",
                                          "setCJKmonofont", "setCJKfamilyfont", "setmathfont", "fontspec"])
                     if a and not a.strip().startswith("\\")]
    # newfontfamily\x{Font}: first arg is a command; take the next group
    for f in info["fonts"]:
        if f["cmd"] in ("newfontfamily", "setCJKfamilyfont"):
            m = re.search(r"\\" + f["cmd"] + r"\s*(\\\w+|\{[^}]*\})\s*(\[[^\]]*\])?\s*\{([^}]*)\}", code)
            if m:
                f["font"] = m.group(3).strip()
    return info, text, lines


def resolve_tex(target, base_dir, root):
    """Resolve an \\input/\\include target to a path (adds .tex)."""
    t = target.strip().strip('"')
    cands = [t] if os.path.splitext(t)[1] in TEX_EXT + (".tikz", ".pgf", ".bbl", ".sty", ".cls") else [t + ".tex", t]
    for base in (base_dir, root):
        for c in cands:
            p = os.path.normpath(os.path.join(base, c))
            if os.path.isfile(p):
                return p
    return None


def resolve_graphic(target, base_dir, root, gpaths):
    t = target.strip().strip('"')
    exts = [""] if os.path.splitext(t)[1].lower() in GRAPHIC_EXT else [".pdf", ".png", ".jpg", ".jpeg", ".eps", ".mps", ".jbig2", ".jb2", ".PDF", ".PNG", ".JPG", ""]
    for base in [base_dir, root] + [os.path.join(base_dir, g) for g in gpaths]:
        for e in exts:
            p = os.path.normpath(os.path.join(base, t + e))
            if os.path.isfile(p):
                return p
    return None


def find_mains(root, files_info):
    mains = []
    for p, inf in files_info.items():
        if inf.get("documentclass") and inf.get("begin_document_line"):
            mains.append(p)
    pref = ("main", "paper", "thesis", "manuscript", "article", "ms", "root", "document", "report")

    def score(p):
        b = os.path.splitext(os.path.basename(p))[0].lower()
        s = 0 if b in pref else 1
        return (s, p.count("/"), -files_info[p]["n_lines"], p)

    return sorted(mains, key=score)


def detect_engine(main_info, all_info):
    """Return (engine, reason)."""
    magic = (main_info.get("magic") or {}).get("program")
    if magic:
        m = magic.lower()
        for e in ("xelatex", "lualatex", "pdflatex", "latex", "uplatex", "platex"):
            if e in m:
                return e, "% !TEX program = " + magic
    pk = {p["name"] for inf in all_info for p in inf["packages"]}
    cls = (main_info.get("documentclass") or {}).get("name", "")
    if pk & {"luatexja", "luatexja-fontspec", "luacode", "luaotfload", "lua-ul", "luatexbase"}:
        return "lualatex", "LuaTeX-only package: " + ", ".join(sorted(pk & {"luatexja", "luatexja-fontspec", "luacode", "luaotfload", "lua-ul"}))
    if pk & {"fontspec", "xeCJK", "unicode-math", "polyglossia", "xltxtra", "xunicode", "mathspec"}:
        return "xelatex", "Unicode-engine package: " + ", ".join(sorted(pk & {"fontspec", "xeCJK", "unicode-math", "polyglossia", "xltxtra", "xunicode", "mathspec"}))
    if cls.startswith("ctex") or "ctex" in pk or cls in ("elegantpaper", "elegantbook", "thuthesis", "ustcthesis", "njuthesis", "sjtuthesis", "fduthesis", "pkuthss", "zjuthesis", "bithesis"):
        return "xelatex", "CJK class/package (ctex family) - XeLaTeX is the usual engine"
    if any(inf["fonts"] for inf in all_info):
        return "xelatex", "fontspec font commands present"
    return "pdflatex", "no Unicode-engine package found"


def detect_bibtool(all_info):
    """Return (tool or None, reason)."""
    pk = {}
    for inf in all_info:
        for p in inf["packages"]:
            pk[p["name"]] = p["options"]
    if "biblatex" in pk:
        opts = ",".join(pk["biblatex"])
        m = re.search(r"backend\s*=\s*(\w+)", opts)
        be = m.group(1) if m else "biber"
        return ("bibtex" if be.startswith("bibtex") else "biber"), "biblatex backend=" + be
    if any(b["cmd"] == "bibliography" for inf in all_info for b in inf["bibs"]):
        return "bibtex", "\\bibliography{...}"
    return None, "no \\bibliography / biblatex"


# ---------------------------------------------------------------- tools


def which(name):
    return shutil.which(name)


def run(cmd, cwd=None, timeout=60, env=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except FileNotFoundError:
        return 127, "", "not found: " + cmd[0]
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode("utf-8", "replace"), "timeout after %ss" % timeout
    except OSError as e:
        return 126, "", str(e)


def tool_version(name):
    if not which(name):
        return None
    flag = "--version" if name not in ("bibtex", "makeindex") else "-version"
    if name == "makeindex":
        return "makeindex (present)"
    code, out, err = run([name, flag], timeout=20)
    first = (out or err).strip().split("\n")[0] if (out or err).strip() else ""
    return first or "present"


def kpsewhich_many(names, cwd=None):
    """Map file name -> path for files kpathsea finds (one call)."""
    names = sorted(set(n for n in names if n))
    found = {}
    if not names or not which("kpsewhich"):
        return found, bool(which("kpsewhich"))
    for i in range(0, len(names), 80):
        chunk = names[i : i + 80]
        code, out, err = run(["kpsewhich"] + chunk, cwd=cwd, timeout=60)
        for line in out.splitlines():
            b = os.path.basename(line.strip())
            for n in chunk:
                if b == n or b.lower() == n.lower():
                    found[n] = line.strip()
    return found, True


def font_lookup(fonts):
    """Map font name -> True/False/None (None = cannot check) via fc-list and kpsewhich fallback."""
    res = {}
    if not fonts:
        return res, None
    fc = which("fc-list")
    blob = ""
    if fc:
        code, out, err = run([fc, ":", "family", "fullname", "file", "postscriptname"], timeout=60)
        blob = out.lower()
    for f in fonts:
        name = f.lower()
        base = re.sub(r"\.(otf|ttf|ttc)$", "", name)
        hit = bool(blob) and ((name in blob) or (base in blob) or (base.replace(" ", "") in blob.replace(" ", "")))
        if not hit:
            # Minimal Linux TeX Live containers often do not index texmf-dist/fonts in fontconfig; check kpsewhich too.
            slug = re.sub(r"[^a-z0-9]", "", base)
            cands = [f] if re.search(r"\.(otf|ttf|ttc)$", name) else [
                f + ".otf", f + ".ttf",
                slug + ".otf", slug + "-regular.otf", slug + "-Regular.otf",
                base.replace(" ", "") + ".otf", base.replace(" ", "") + "-Regular.otf",
                base.replace(" ", "") + ".ttf", base.replace(" ", "") + "-Regular.ttf",
            ]
            k, _ = kpsewhich_many(cands)
            hit = bool(k)
        if not hit and not fc:
            res[f] = None
        else:
            res[f] = hit
    return res, fc


def tex_env(extra=None):
    env = dict(os.environ)
    env.update({"max_print_line": "10000", "error_line": "254", "half_error_line": "238", "TEXMFOUTPUT": "", "LC_ALL": env.get("LC_ALL", "C.UTF-8")})
    if os.name == "nt":
        env.pop("LC_ALL", None)
    if extra:
        env.update(extra)
    return env


def summarize_case(case):
    """Find case id, output contract and declared inputs in an arbitrary case.json."""
    cid = None
    for k in ("case_id", "id", "caseId", "case", "name"):
        if isinstance(case.get(k), (str, int)):
            cid = str(case[k])
            break
    contract = None
    for k in ("output_contract", "outputs", "output", "expected_output", "deliverables", "output_schema"):
        if k in case:
            contract = case[k]
            break
    return cid, contract


def contract_fields(contract):
    if isinstance(contract, dict):
        if "schema" in contract and isinstance(contract["schema"], dict):
            return contract_fields(contract["schema"])
        if "fields" in contract and isinstance(contract["fields"], (list, dict)):
            return contract_fields(contract["fields"])
        if "properties" in contract and isinstance(contract["properties"], dict):
            return list(contract["properties"].keys())
        if "required" in contract and isinstance(contract["required"], list) and len(contract) <= 3:
            return [str(x) for x in contract["required"]]
        return list(contract.keys())
    if isinstance(contract, list):
        out = []
        for x in contract:
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                for k in ("name", "field", "key", "id"):
                    if k in x:
                        out.append(str(x[k]))
                        break
        return out
    if isinstance(contract, str):
        return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", contract)
    return []


def inspect_cls(path):
    """Extract declared options, commands, required checks, and ClassError/Warning hints from a local .cls/.sty."""
    text, _ = read_text(path)
    base_class = None
    m = re.search(r"\\LoadClass(?:\[[^\]]*\])?\{([^}]+)\}", text)
    if m:
        base_class = m.group(1).strip()
    options = sorted(set(re.findall(r"\\DeclareOption\*?\{([^}]+)\}", text)))[:25]
    cmds = sorted(set(re.findall(r"\\(?:newcommand|renewcommand|providecommand|def)\s*\\([A-Za-z][A-Za-z0-9]*)", text)))
    cmds = [c for c in cmds if not c.startswith("@")][:35]
    errs = [re.sub(r"\s+", " ", x).strip()[:120] for x in re.findall(r"\\Class(?:Error|Warning(?:NoLine)?)\{[^}]*\}\{([^}]*)\}", text)][:10]
    pkgs = sorted(set(p for g in re.findall(r"\\RequirePackage(?:\[[^\]]*\])?\{([^}]+)\}", text) for p in split_csv(g)))[:25]
    return {"base_class": base_class, "options": options, "commands": cmds, "requires": pkgs, "checks": errs}


def extract_pdf_text(path):
    """Best-effort text extraction from an input material PDF using pdftotext or PyMuPDF (if installed)."""
    if which("pdftotext"):
        code, out, _ = run(["pdftotext", "-enc", "UTF-8", path, "-"], timeout=30)
        if code == 0 and out.strip():
            return out
    try:
        import fitz  # optional
        with fitz.open(path) as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except Exception:
        return ""
