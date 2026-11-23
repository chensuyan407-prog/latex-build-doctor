"""Parse TeX / BibTeX / Biber logs into located, classified diagnostics with root-cause grouping."""
import os
import re

from lx_common import load_rules

_PKGS = None


def pkg_rules():
    global _PKGS
    if _PKGS is None:
        _PKGS = load_rules("packages.json")
    return _PKGS


# class, severity, regex on the error message, hint template
ERROR_CLASSES = [
    ("missing_class", r"LaTeX Error: File `([^']+)\.cls' not found", "Document class file {0}.cls is missing: copy the template's .cls into the project root (next to the main .tex) or install it; do not switch to another class silently."),
    ("missing_package", r"LaTeX Error: File `([^']+)\.sty' not found", "Package {0}.sty is not installed or misspelled. Check the name; if it is a template-local package, copy it into the project; else install (tlmgr install <pkg>) or remove the \\usepackage and its commands."),
    ("missing_file", r"LaTeX Error: File `([^']+)' not found", "File '{0}' was not found: check path/case/extension relative to the main file and \\graphicspath."),
    ("missing_file", r"! I can't find file `([^']+)'", "Input file '{0}' not found: check the \\input/\\include path (relative to the main file, case-sensitive on Linux)."),
    ("missing_file", r"Package (?:pdftex\.def|graphics|xetex\.def|luatex\.def) Error: File `([^']+)' not found", "Graphic '{0}' not found: check path/case/extension and \\graphicspath."),
    ("missing_font", r'fontspec Error: The font "([^"]+)" cannot be found', "Font '{0}' is not installed on this system. Use an installed font (check with fc-list) or ship the font file and load it by file name with Path=; record the substitution."),
    ("missing_font", r"Font \\[^=]+=([^ ]+) (?:at [^ ]+ )?not loadable: Metric \(TFM\) file not found", "TFM for font '{0}' not found: the font package is missing or the font name is wrong."),
    ("missing_font", r"Font \\[^=]+=\"?([^\" ]+).* not loadable", "Font '{0}' cannot be loaded."),
    ("engine_mismatch", r"fontspec Error: The fontspec package requires either XeTeX or LuaTeX", "fontspec needs XeLaTeX or LuaLaTeX: build with --engine xelatex (or add '% !TEX program = xelatex' to the main file)."),
    ("engine_mismatch", r"(?:xeCJK|unicode-math|polyglossia) Error: .*(?:XeTeX|LuaTeX)", "This package needs XeLaTeX/LuaLaTeX: switch the engine."),
    ("engine_mismatch", r"(?:ctex\w*|CTeX) .*(?:unavailable in .*current mode|engine)|ctex Error: .*Unknown option", "ctex engine/option problem: build ctex documents with XeLaTeX (or LuaLaTeX)."),
    ("unicode_char", r"(?:LaTeX|inputenc) Error: (?:Unicode character|Invalid UTF-8 byte|Keyboard character) (.*?)(?: not set up| used| sequence|$)", "Non-ASCII character {0} not supported under pdfLaTeX with this font: replace it with a LaTeX command, add the right package, or build with XeLaTeX if the document is meant to be Unicode."),
    ("undefined_cs", r"Undefined control sequence", "Undefined command {cs}: {why}"),
    ("undefined_env", r"LaTeX Error: Environment ([^ ]+) undefined", "Environment '{0}' is undefined: {why}"),
    ("env_mismatch", r"LaTeX Error: \\begin\{([^}]*)\} on input line (\d+) ended by \\end\{([^}]*)\}", "environment '{0}' (opened line {1}) is closed by an \\end of '{2}': an \\end is missing/misspelled, or '{0}' was opened inside a group or an undefined environment."),
    ("env_mismatch", r"LaTeX Error: \\begin\{([^}]*)\} ended by \\end\{([^}]*)\}", "environment '{0}' is closed by an \\end of '{1}'."),
    ("env_mismatch", r"LaTeX Error: Bad math environment delimiter", "Math delimiters do not pair (\\[ \\], \\( \\), $ $)."),
    ("math_mode", r"Missing \$ inserted", "Math-only material in text mode (often _ ^ \\alpha \\frac or & outside $...$), or a blank line inside display math. Wrap the math in $...$ / escape \\_ in text."),
    ("math_mode", r"Display math should end with \$\$", "Display math opened with $$ is not closed properly; use \\[...\\]."),
    ("math_mode", r"LaTeX Error: Command \\\\?[A-Za-z]+ invalid in math mode", "Text-mode command used inside math."),
    ("math_mode", r"Please use \\mathaccent for accents in math mode", "Text accent used in math; use \\hat, \\tilde, ... ."),
    ("brace", r"Missing \} inserted", "A group is not closed (missing '}') or math/alignment ended inside a group."),
    ("brace", r"Missing \{ inserted", "A '{' is expected here (often a subscript/superscript or \\frac argument missing braces, or a '}' too many)."),
    ("brace", r"Too many \}'s", "Unbalanced '}' - one closing brace too many."),
    ("brace", r"Extra \}, or forgotten (\$|\\endgroup|\\right|\\end\w*)", "An extra '}' or a missing {0}."),
    ("brace", r"Extra \\right", "\\right without \\left (or split over an & / \\\\ boundary)."),
    ("brace", r"Missing \\right\. inserted|Missing \\right inserted", "\\left without \\right (add \\right. or check line breaks inside \\left...\\right)."),
    ("brace", r"Argument of \\([A-Za-z@]+) has an extra \}", "Argument of \\{0} has an extra '}'."),
    ("runaway", r"Runaway argument|File ended while scanning use of \\?([A-Za-z@]*)|Paragraph ended before \\([A-Za-z@]+) was complete", "Unclosed argument (missing '}') - the error is reported where TeX gave up, the cause is at the opening of the argument (see static brace check)."),
    ("no_end", r"\*\*\* \(job aborted, no legal \\end found\)|LaTeX Error: \\begin\{document\} ended by \\end\{([^}]*)\}|Emergency stop.*end of file|\(\\end occurred inside a group", "Document ends inside an open group/environment: see the env/brace checks for the opening line."),
    ("alignment", r"Misplaced alignment tab character &", "'&' outside a tabular/align (escape it as \\& in text)."),
    ("alignment", r"Extra alignment tab has been changed to \\cr", "A table row has more cells than the column spec: add a column to the spec or remove a '&'."),
    ("alignment", r"Misplaced \\(?:noalign|omit|cr|crcr)", "\\hline/\\midrule/\\multicolumn in the wrong place (must follow \\\\ or start a row)."),
    ("alignment", r"Illegal pream-token|LaTeX Error: Illegal character in array arg|Unknown column type", "Invalid column specifier in the tabular preamble (e.g. S needs siunitx, X needs tabularx, wrong p{...})."),
    ("alignment", r"LaTeX Error: There's no line here to end", "\\\\ (or \\newline) at a place with no line, e.g. after a blank line or at the start of a paragraph/list item."),
    ("alignment", r"Only one # is allowed per tab", "Bad column spec / macro parameter inside alignment."),
    ("number_unit", r"Illegal unit of measure|Missing number, treated as zero", "A length/number is malformed (e.g. width=0.5 without \\linewidth, or an empty optional argument)."),
    ("option_clash", r"LaTeX Error: Option clash for package ([^ .]+)", "Package {0} is loaded twice with different options (possibly by the class or another package): load it once with all options before the other package, or pass options via \\PassOptionsToPackage before \\documentclass."),
    ("already_defined", r"LaTeX Error: Command \\([^ ]+) already defined|Command \\([^ ]+) already defined", "\\{0} is defined twice - two packages conflict or \\newcommand should be \\renewcommand / \\providecommand."),
    ("bad_option", r"LaTeX Error: Unknown option `([^']+)' for (?:package|class) `([^']+)'", "Option '{0}' is not valid for {1}."),
    ("key_error", r"Package (?:pgfkeys|keyval|xkeyval|l3keys|kvsetkeys|siunitx|caption|hyperref|geometry|enumitem|tcolorbox|tabularray) Error: (.*)", "Key/option error: {0}"),
    ("float", r"LaTeX Error: (?:Too many unprocessed floats|Float\(s\) lost)", "Too many floats or a float inside a box/minipage/marginpar; add \\clearpage / FloatBarrier or move the float out of the box."),
    ("float", r"LaTeX Error: Not in outer par mode", "A float (figure/table) or \\marginpar inside a box, minipage or another float."),
    ("float", r"LaTeX Error: \\caption outside float", "\\caption outside a figure/table (use \\captionof from caption/capt-of)."),
    ("structure", r"LaTeX Error: Something's wrong--perhaps a missing \\item", "List environment without \\item, or \\\\ / text directly in a list/description."),
    ("structure", r"LaTeX Error: Lonely \\item--perhaps a missing list environment", "\\item outside itemize/enumerate."),
    ("structure", r"LaTeX Error: Can be used only in preamble", "Preamble-only command (\\usepackage, \\documentclass...) used after \\begin{document}."),
    ("structure", r"LaTeX Error: Missing \\begin\{document\}", "Text or a bad command in the preamble (often a stray character or a .tex file with content loaded with \\usepackage)."),
    ("structure", r"LaTeX Error: \\include cannot be nested|\\include.*preamble", "\\include inside an \\include'd file or in the preamble; use \\input."),
    ("structure", r"You can't use `([^']+)' in (vertical|horizontal|math|restricted horizontal|internal vertical) mode", "{0} is not allowed in {1} mode."),
    ("structure", r"Undefined color `([^']+)'", "Color '{0}' is undefined: define it with \\definecolor or load xcolor with the dvipsnames/svgnames option."),
    ("permission", r"I can't write on file `([^']+)'|Permission denied|not writable|cannot open .* for writing", "Cannot write '{0}': the output directory is read-only or the file is open in another program; build in a writable directory (the build script uses work/build)."),
    ("permission", r"Not writing to .* \(openout_any = p\)", "TeX refused to write outside the build directory (openout_any=p); write auxiliary files to the current directory."),
    ("shell_escape", r"Package (?:minted|svg|pythontex|gnuplottex|epstopdf) Error: .*(?:shell.escape|-shell-escape|write18)", "This package needs -shell-escape (security risk; only if the source is trusted). Rerun build with --shell-escape or pre-render the content."),
    ("capacity", r"TeX capacity exceeded, sorry \[([^\]]+)\]", "TeX capacity exceeded ({0}): usually infinite recursion (a macro calling itself, \\renewcommand loop, missing } in a macro), not a real memory limit."),
    ("bib_engine", r"Package biblatex Error: '([^']+)' not found|biblatex Error: Incompatible", "biblatex and biber versions or backend do not match: run biber (not bibtex) or set backend=bibtex."),
    ("generic_error", r"LaTeX Error: (.*)", "{0}"),
    ("generic_error", r"Package (\S+) Error: (.*)", "{0}: {1}"),
    ("generic_error", r"Class (\S+) Error: (.*)", "{0}: {1}"),
    ("generic_error", r"(.*)", "{0}"),
]
ERROR_CLASSES = [(c, re.compile(p), h) for c, p, h in ERROR_CLASSES]

ROOT_RANK = {"missing_class": 0, "missing_package": 1, "engine_mismatch": 1, "missing_font": 2, "permission": 2, "missing_file": 3,
             "option_clash": 4, "already_defined": 4, "unicode_char": 5, "runaway": 5, "no_end": 6, "env_mismatch": 6, "brace": 7,
             "undefined_env": 6, "undefined_cs": 6, "math_mode": 7, "alignment": 7, "structure": 7, "float": 8, "number_unit": 8,
             "bad_option": 5, "key_error": 6, "shell_escape": 3, "capacity": 5, "bib_engine": 3, "generic_error": 9, "timeout": 5}

WARNINGS = [
    ("undefined_ref", "warning", re.compile(r"LaTeX Warning: Reference `([^']*)' on page \S+ undefined(?: on input line (\d+))?")),
    ("undefined_ref", "warning", re.compile(r"Package (?:cleveref|hyperref) Warning: Reference `([^']*)' on page \S+ undefined(?: on input line (\d+))?")),
    ("undefined_ref", "warning", re.compile(r"LaTeX Warning: Hyper reference `([^']*)' on page \S+ undefined(?: on input line (\d+))?")),
    ("undefined_cite", "warning", re.compile(r"(?:LaTeX|Package natbib) Warning: Citation [`']([^']*)' on page \S+ undefined(?: on input line (\d+))?")),
    ("undefined_cite", "warning", re.compile(r"Package biblatex Warning: The following entry could not be found\s*\(biblatex\)\s*in the database:\s*\(biblatex\)\s*(\S+)")),
    ("duplicate_label", "warning", re.compile(r"LaTeX Warning: Label `([^']*)' multiply defined")),
    ("rerun", "info", re.compile(r"(LaTeX Warning: Label\(s\) may have changed|Rerun to get|Please rerun LaTeX|Package biblatex Warning: Please \(re\)run Biber|Package rerunfilecheck Warning|LaTeX Warning: There were undefined references|Package natbib Warning: There were undefined citations|Please \(re\)run Biber)")),
    ("float_too_large", "warning", re.compile(r"LaTeX Warning: Float too large for page by ([\d.]+pt) on input line (\d+)")),
    ("float_spec", "info", re.compile(r"LaTeX Warning: `(!?h)' float specifier changed to `([^']+)'")),
    ("font_substitution", "warning", re.compile(r"LaTeX Font Warning: Font shape `([^']+)' undefined")),
    ("font_size_substitution", "info", re.compile(r"LaTeX Font Warning: Font shape `([^']+)' in size \S+ not available")),
    ("missing_glyph", "warning", re.compile(r"Missing character: There is no (.+?) (?:\(U\+([0-9A-Fa-f]+)\) )?in font ([^!]+)!")),
    ("unused_option", "info", re.compile(r"LaTeX Warning: Unused global option\(s\):\s*\[?([^\]]*)")),
    ("pdf_string", "info", re.compile(r"Package hyperref Warning: Token not allowed in a PDF string")),
    ("empty_bib", "warning", re.compile(r"(?:LaTeX Warning: Empty `thebibliography' environment|Package biblatex Warning: Empty bibliography)")),
    ("obsolete", "info", re.compile(r"(?:Package|Class) (\S+) Warning: .*(?:obsolete|deprecated)", re.I)),
    ("package_warning", "info", re.compile(r"(?:Package|Class) (\S+) Warning: (.*)")),
    ("latex_warning", "info", re.compile(r"LaTeX Warning: (.*)")),
]

BOX = re.compile(r"^(Overfull|Underfull) \\([hv])box \((?:(\d+(?:\.\d+)?)pt too (wide|high)|badness (\d+))\) (?:in paragraph|in alignment|detected|has occurred while \\output is active)(?: at lines? (\d+)(?:--(\d+))?)?")
FLE = re.compile(r"^(.*?\.(?:tex|ltx|sty|cls|bbl|aux|def|cfg|clo|tikz|pgf|toc|lof|lot|ind|gls|nls|bib|dtx|fd|out|nav|snm|vrb)):(\d+): (.*)$")
FILE_TOKEN = re.compile(r"\(\"?((?:[A-Za-z]:)?[^()\s\"]*?\.[A-Za-z0-9]{1,8})\"?(?=[\s()\"]|$)")


class FileStack:
    """Tracks which file TeX is reading from the '(' / ')' structure of an unwrapped log."""

    def __init__(self):
        self.stack = []

    def feed(self, line):
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "(":
                m = FILE_TOKEN.match(line, i)
                if m:
                    self.stack.append(m.group(1))
                    i = m.end()
                    continue
                self.stack.append(None)
            elif ch == ")":
                if self.stack:
                    self.stack.pop()
            i += 1

    def current(self):
        for f in reversed(self.stack):
            if f and not re.search(r"\.(sty|cls|def|cfg|clo|fd|aux|out|toc|lof|lot|map|enc|pfb|tfm|vf|otf|ttf|ldf|dict|bbx|cbx|lbx|ltx)$", f, re.I):
                return f
        return None


def _norm(f, project_files):
    if not f:
        return None
    g = f.replace("\\", "/")
    g = re.sub(r"^\./", "", g)
    if g in project_files:
        return g
    for p in project_files:
        if g.endswith("/" + p) or p.endswith("/" + g) or os.path.splitext(p)[0] == g:
            return p
    return g if "/" not in g or not os.path.isabs(g) else None


def _cs_from_context(before):
    m = re.search(r"(\\[A-Za-z@]+\*?|\\.)\s*$", before)
    return m.group(1).rstrip("*") if m else None


def explain_cs(cs, defined_cmds, loaded):
    r = pkg_rules()["commands"]
    name = cs.lstrip("\\")
    if name in r:
        pkg = r[name]
        base = re.split(r"[ \[(]", pkg)[0]
        if pkg.startswith("("):
            return "%s %s" % (cs, pkg[1:-1] if pkg.endswith(")") else pkg), None
        if base in loaded:
            return "%s comes from %s, which is loaded - check its version/options or the spelling." % (cs, pkg), base
        return "%s is provided by package %s, which is not loaded: add \\usepackage{%s} to the preamble (check the template allows it)." % (cs, pkg, base), base
    import difflib
    cands = difflib.get_close_matches(name, list(defined_cmds) + list(r.keys()), n=3, cutoff=0.75)
    if cands:
        return "%s is unknown - likely a typo of %s." % (cs, ", ".join("\\" + c for c in cands)), None
    return "%s is not defined by any loaded package or \\newcommand in the project; define it or remove it." % cs, None


def explain_env(env, loaded):
    r = pkg_rules()["environments"]
    if env in r:
        pkg = r[env]
        base = re.split(r"[ \[(]", pkg)[0]
        if pkg.startswith("("):
            return pkg.strip("()"), None
        if base in loaded:
            return "provided by %s (loaded) - check spelling/options." % pkg, base
        return "provided by package %s, which is not loaded: add \\usepackage{%s}." % (pkg, base), base
    return "not defined; check the spelling or define it (\\newenvironment / \\newtheorem).", None


def parse_tex_log(text, project_files, loaded_pkgs=(), defined_cmds=()):
    """Return (diagnostics, info). project_files: list of project-relative paths."""
    lines = text.replace("\r\n", "\n").split("\n")
    fs = FileStack()
    diags = []
    info = {"packages": {}, "documentclass": None, "pdf_pages": None, "output": None, "fatal": False, "rerun": False, "engine_banner": lines[0] if lines else ""}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r"^(Package|Document Class|File): (\S+) (\d{4}[/-]\d\d[/-]\d\d)\s*(.*)$", line)
        if m:
            k = m.group(2)
            if m.group(1) == "Document Class":
                info["documentclass"] = {"name": k, "date": m.group(3), "version": m.group(4).strip()}
            elif m.group(1) == "Package":
                info["packages"][k] = {"date": m.group(3), "version": m.group(4).strip()}
        m = re.match(r"^Output written on (.+?) \((\d+) pages?", line)
        if m:
            info["output"], info["pdf_pages"] = m.group(1), int(m.group(2))
        if "no output PDF file produced" in line or "job aborted" in line or line.startswith("! Emergency stop") or "==> Fatal error" in line:
            info["fatal"] = True
        fle = FLE.match(line)
        if fle or line.startswith("! "):
            raised_in = None
            if fle:
                efile, eline, msg = _norm(fle.group(1), project_files), int(fle.group(2)), fle.group(3).strip()
                if efile is None or re.search(r"\.(sty|cls|def|cfg|clo|fd|ltx)$", efile):
                    raised_in = os.path.basename(fle.group(1).replace("\\", "/"))
                    efile, eline = _norm(fs.current(), project_files), None
            else:
                efile, eline, msg = _norm(fs.current(), project_files), None, line[2:].strip()
            block = [msg]
            ctx_before = ctx_after = None
            j = i + 1
            while j < n and j < i + 40:
                lj = lines[j]
                mm = re.match(r"^l\.(\d+) (.*)$", lj)
                if mm:
                    if eline is None and not raised_in:
                        eline = int(mm.group(1))
                    ctx_before = mm.group(2)
                    ctx_after = lines[j + 1].strip() if j + 1 < n else ""
                    j += 2
                    break
                if FLE.match(lj) or lj.startswith("! ") or lj.startswith("Here is how much") or lj.startswith("(see the transcript"):
                    break
                block.append(lj)
                j += 1
            full = re.sub(r"\s+", " ", " ".join(re.sub(r"^\([\w@-]+\)\s*", "", b.strip()) for b in block if b.strip()))
            if msg.startswith("Emergency stop") or msg.startswith("==> Fatal error"):
                info["fatal"] = True
                for x in block[1:]:
                    fs.feed(x)
                i = max(j, i + 1)
                continue
            d = classify_error(full, msg, ctx_before, ctx_after, loaded_pkgs, defined_cmds)
            if raised_in:
                d["raised_in"] = raised_in
            d.update({"file": efile, "line": eline, "context": ((ctx_before or "") + " <HERE> " + (ctx_after or "")).strip() if ctx_before is not None else None})
            diags.append(d)
            for x in block[1:]:
                fs.feed(x)
            i = max(j, i + 1)
            continue
        bm = BOX.match(line)
        if bm:
            kind, hv, amount, wh, bad, l1, l2 = bm.groups()
            if kind == "Overfull" and amount and float(amount) > 1.0:
                diags.append({"class": "overfull_box", "severity": "warning", "message": line.strip(), "file": _norm(fs.current(), project_files),
                              "line": int(l1) if l1 else None, "line_end": int(l2) if l2 else None, "amount_pt": float(amount),
                              "in_alignment": "in alignment" in line,
                              "hint": ("Table/alignment wider than the column by %spt: use tabularx/p{} columns, shorter headers, \\small, or a table* - not \\resizebox." % amount) if "alignment" in line
                              else "Line sticks out by %spt: rephrase, allow hyphenation (\\-), break a long URL/formula, or \\sloppypar locally." % amount})
            fs.feed(line)
            i += 1
            continue
        # warnings may continue on following lines prefixed with "(pkgname)"
        wtext = line
        k = i + 1
        if re.match(r"^(LaTeX|Package|Class) .*Warning", line) or line.startswith("LaTeX Font Warning"):
            while k < n and re.match(r"^\(\S+\)\s+", lines[k]):
                wtext += " " + re.sub(r"^\(\S+\)\s+", "", lines[k])
                k += 1
            for cls, sev, rx in WARNINGS:
                wm = rx.search(wtext)
                if wm:
                    if cls == "rerun":
                        info["rerun"] = True
                    ln = None
                    lm = re.search(r"on input line (\d+)", wtext)
                    if lm:
                        ln = int(lm.group(1))
                    d = {"class": cls, "severity": sev, "message": wtext.strip()[:400], "file": _norm(fs.current(), project_files), "line": ln}
                    if cls in ("undefined_ref", "undefined_cite", "duplicate_label"):
                        d["key"] = wm.group(1)
                    if cls == "missing_glyph":
                        d["char"], d["font"] = wm.group(1) + (" (U+%s)" % wm.group(2).upper() if wm.group(2) else ""), wm.group(3).strip()
                        d["hint"] = "Glyph %s missing in font %s - it will be blank in the PDF. Use a font that has it (CJK: ctex/xeCJK with an installed CJK font)." % (wm.group(1), d["font"])
                    if cls == "float_too_large":
                        d["hint"] = "Float taller than the text block by %s: reduce the figure height (e.g. height=0.8\\textheight) or split the table (longtable)." % wm.group(1)
                    if cls == "font_substitution":
                        d["hint"] = "Font shape %s not available; a default was substituted (bold/italic of this font may be missing)." % wm.group(1)
                    diags.append(d)
                    break
            for x in lines[i:k]:
                fs.feed(x)
            i = k
            continue
        if line.startswith("Missing character: There is no"):
            wm = [w for w in WARNINGS if w[0] == "missing_glyph"][0][2].search(line)
            if wm:
                diags.append({"class": "missing_glyph", "severity": "warning", "message": line.strip(), "file": _norm(fs.current(), project_files), "line": None,
                              "char": wm.group(1) + (" (U+%s)" % wm.group(2).upper() if wm.group(2) else ""), "font": wm.group(3).strip(),
                              "hint": "Glyph %s missing in font %s - it will be blank in the PDF." % (wm.group(1), wm.group(3).strip())})
            i += 1
            continue
        fs.feed(line)
        i += 1
    group_roots(diags)
    return diags, info


def fmt(t, g, **kw):
    for i, v in enumerate(g):
        t = t.replace("{%d}" % i, v)
    for k, v in kw.items():
        t = t.replace("{%s}" % k, str(v))
    return t.replace("<", "{").replace(">", "}") if "\begin<" in t else t


def classify_error(full, msg, before, after, loaded, defined):
    for cls, rx, hint in ERROR_CLASSES:
        m = rx.search(full) or rx.search(msg)
        if not m:
            continue
        g = [x or "" for x in m.groups()]
        d = {"class": cls, "severity": "error", "message": full[:500]}
        if cls == "undefined_cs":
            cs = _cs_from_context(before or "")
            why, pkg = explain_cs(cs, defined, loaded) if cs else ("see the context line; the last command before the line break is undefined.", None)
            d["cs"] = cs
            if pkg:
                d["needs_package"] = pkg
            d["hint"] = fmt(hint, [], cs=cs or "?", why=why)
        elif cls == "undefined_env":
            why, pkg = explain_env(g[0], loaded)
            d["env"] = g[0]
            if pkg:
                d["needs_package"] = pkg
            d["hint"] = fmt(hint, g, why=why)
        else:
            d["hint"] = fmt(hint, g)
        if cls in ("missing_package", "missing_class"):
            d["name"] = g[0]
        if cls == "missing_file":
            d["name"] = g[0]
        if cls == "missing_font":
            d["font"] = g[0]
        if cls == "option_clash":
            d["name"] = g[0]
        return d
    return {"class": "generic_error", "severity": "error", "message": full[:500], "hint": full[:200]}


def group_roots(diags):
    """Mark follow-on errors (cascade_of = index of the root) so the agent fixes causes, not symptoms."""
    errs = [k for k, d in enumerate(diags) if d["severity"] == "error"]
    for k in range(len(diags)):
        diags[k]["id"] = "E%03d" % (k + 1) if diags[k]["severity"] == "error" else "W%03d" % (k + 1)
    seen_cs, seen_pkg, seen_msg = {}, {}, {}
    missing_pkgs = {d.get("name"): k for k, d in enumerate(diags) if d["class"] == "missing_package"}
    follow = {"math_mode": {"math_mode", "brace", "generic_error", "number_unit"},
              "brace": {"brace", "math_mode", "generic_error", "runaway"},
              "undefined_cs": {"generic_error", "number_unit", "math_mode", "brace"},
              "env_mismatch": {"env_mismatch", "no_end", "structure"},
              "undefined_env": {"env_mismatch", "no_end", "structure", "alignment", "generic_error", "math_mode", "brace"},
              "alignment": {"generic_error", "brace", "math_mode"},
              "missing_font": {"missing_font", "generic_error"},
              "unicode_char": {"generic_error"}}
    prev = None
    last_env = None
    for k in errs:
        d = diags[k]
        root = None
        key = d.get("cs") or d.get("env")
        if d["class"] == "undefined_cs" and d.get("needs_package") in missing_pkgs:
            root = missing_pkgs[d["needs_package"]]
        elif d["class"] in ("undefined_cs", "undefined_env") and key in seen_cs:
            root = seen_cs[key]  # same command again
        elif d["class"] in ("undefined_cs", "undefined_env") and d.get("needs_package") and d["needs_package"] in seen_pkg:
            root = seen_pkg[d["needs_package"]]  # another command of the same missing package
        elif d["class"] == "engine_mismatch" and "engine" in seen_pkg:
            root = seen_pkg["engine"]
        elif d["class"] not in ("undefined_cs", "undefined_env") and (d["class"], d["message"][:60], d.get("file")) in seen_msg:
            root = seen_msg[(d["class"], d["message"][:60], d.get("file"))]  # identical error repeated (e.g. every table row)
        if root is None and prev is not None:
            p = diags[prev]
            same_file = p.get("file") == d.get("file")
            dl = (d["line"] - p["line"]) if same_file and p.get("line") is not None and d.get("line") is not None else None
            if dl is not None and 0 <= dl <= 1 and d["class"] in follow.get(p["class"], set()):
                root = p.get("cascade_of_idx", prev)
            elif p["class"] == "undefined_env" and dl is not None and 0 <= dl <= 40 and d["class"] in follow["undefined_env"]:
                root = p.get("cascade_of_idx", prev)
        if root is None and last_env is not None:
            u = diags[last_env]
            if u.get("file") == d.get("file") and u.get("line") and d.get("line") and 0 <= d["line"] - u["line"] <= 40 and \
                    d["class"] in ("undefined_cs", "env_mismatch", "alignment", "structure", "generic_error", "no_end"):
                root = last_env  # commands/ends inside an environment that does not exist
            elif p["class"] in ("runaway", "capacity", "no_end") and (same_file or d["class"] in ("no_end", "runaway")):
                root = p.get("cascade_of_idx", prev)
            elif d["class"] == "no_end":
                root = p.get("cascade_of_idx", prev)
        if root is None:
            if key and d["class"] in ("undefined_cs", "undefined_env"):
                seen_cs.setdefault(key, k)
                if d.get("needs_package"):
                    seen_pkg.setdefault(d["needs_package"], k)
            seen_msg.setdefault((d["class"], d["message"][:60], d.get("file")), k)
            if d["class"] == "engine_mismatch":
                seen_pkg.setdefault("engine", k)
            if d["class"] == "undefined_env":
                last_env = k
        if root is not None and root != k:
            d["cascade_of_idx"] = root
            d["cascade_of"] = diags[root]["id"]
        prev = k
    # several independent-looking errors at the same file:line -> one root (the most specific class)
    pref = {"undefined_cs": 0, "undefined_env": 0, "brace": 1, "runaway": 1, "math_mode": 2, "env_mismatch": 2, "alignment": 3, "number_unit": 4, "structure": 5, "generic_error": 6}
    at = {}
    for k in errs:
        d = diags[k]
        if d.get("cascade_of") or not d.get("line"):
            continue
        at.setdefault((d.get("file"), d["line"]), []).append(k)
    for ks in at.values():
        if len(ks) < 2:
            continue
        root = min(ks, key=lambda k: (pref.get(diags[k]["class"], 5), k))
        for k in ks:
            if k != root and pref.get(diags[k]["class"], 5) >= 3:
                diags[k]["cascade_of"] = diags[root]["id"]
    for d in diags:
        d.pop("cascade_of_idx", None)


def parse_bibtex_blg(text, bib_files):
    diags = []
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^I couldn't open (database|style|auxiliary) file (.+)$", line)
        if m:
            diags.append({"class": "bib_missing_file", "severity": "error", "message": line, "file": None, "line": None,
                          "hint": "BibTeX cannot open %s file %s: check the name in \\bibliography{}/\\bibliographystyle{} (no .bib extension needed) and that it is in the project." % (m.group(1), m.group(2))})
            continue
        m = re.match(r"^Warning--I didn't find a database entry for \"([^\"]+)\"", line)
        if m:
            diags.append({"class": "undefined_cite", "severity": "warning", "message": line, "key": m.group(1), "file": None, "line": None, "source": "bibtex"})
            continue
        m = re.match(r"^Warning--(empty|missing) (\w+) in (\S+)", line)
        if m:
            diags.append({"class": "bib_field", "severity": "warning", "message": line, "key": m.group(3), "field": m.group(2), "file": None, "line": None,
                          "hint": "Entry %s has no %s field: complete it from the source (do not invent)." % (m.group(3), m.group(2))})
            continue
        m = re.match(r"^Repeated entry---line (\d+) of file (\S+)", line)
        if m:
            diags.append({"class": "bib_duplicate", "severity": "error", "message": line + " " + (lines[i + 1] if i + 1 < len(lines) else ""), "file": _bibrel(m.group(2), bib_files), "line": int(m.group(1)),
                          "hint": "Duplicate BibTeX key - the second entry is ignored. Merge or rename."})
            continue
        m = re.search(r"---line (\d+) of file (\S+)", line)
        if m and i > 0:
            msg = lines[i - 1].strip() + " " + line.strip()
            diags.append({"class": "bib_syntax", "severity": "error", "message": msg, "file": _bibrel(m.group(2), bib_files), "line": int(m.group(1)),
                          "hint": "BibTeX syntax error (missing comma/brace/quote or illegal character in a key); entries after it may be skipped."})
            continue
        m = re.match(r"^(?:Warning--)?(.*) in (\S+)$", line)
        if line.startswith("Warning--") and m:
            diags.append({"class": "bib_warning", "severity": "info", "message": line, "file": None, "line": None})
    return diags


def _bibrel(name, bib_files):
    b = os.path.basename(name)
    for f in bib_files:
        if os.path.basename(f) == b or os.path.splitext(os.path.basename(f))[0] == os.path.splitext(b)[0]:
            return f
    return name


def parse_biber_blg(text, bib_files):
    diags = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^\[\d+\] [\w:]+> (ERROR|WARN) - (.*)$", line)
        if not m:
            continue
        sev, msg = m.groups()
        d = {"class": "bib_error" if sev == "ERROR" else "bib_warning", "severity": "error" if sev == "ERROR" else "warning", "message": msg, "file": None, "line": None}
        lm = re.search(r"(?:line|ln) (\d+)", msg)
        fm = re.search(r"([^\s/\\]+\.bib)", msg)
        if fm:
            d["file"] = _bibrel(fm.group(1), bib_files)
        if lm:
            d["line"] = int(lm.group(1))
        km = re.search(r"I didn't find a database entry for '([^']+)'", msg)
        if km:
            d.update({"class": "undefined_cite", "key": km.group(1), "severity": "warning", "source": "biber"})
        elif "Cannot find" in msg or "Data source" in msg and "not found" in msg:
            d["class"] = "bib_missing_file"
            d["hint"] = "Biber cannot find the .bib file: check \\addbibresource{name.bib} (extension required)."
        elif sev == "ERROR":
            d["class"] = "bib_syntax"
            d["hint"] = "Biber could not parse the .bib (see line): fix the entry syntax."
        elif "Duplicate entry key" in msg:
            d["class"] = "bib_duplicate"
        diags.append(d)
    return diags
