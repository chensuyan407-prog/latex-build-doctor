"""Conservative repair proposals for the staged, reachable TeX sources."""
import os
import re
from pathlib import Path

from lx_common import VERB_ENVS, load_rules, strip_comment, which, run

_CORE_PACKAGES = ("amsmath", "booktabs", "graphicx", "tabularx", "hyperref")


def _load_known_packages():
    rules = load_rules("packages.json")
    seen = list(_CORE_PACKAGES)
    seen_set = set(seen)
    for section in ("commands", "environments"):
        for val in (rules.get(section) or {}).values():
            if not isinstance(val, str) or val.startswith("(") or " class" in val:
                continue
            pkg = val.split()[0].split("[")[0].strip()
            if pkg and pkg not in seen_set:
                seen_set.add(pkg)
                seen.append(pkg)
    return tuple(seen)


PACKAGES = _load_known_packages()
CHKTEX_NOISE_RULES = {1, 2, 3, 8, 12, 13, 18, 24, 26, 36, 44}
ENV = re.compile(r"\\(begin|end)\s*\{([\w*]+)\}")
MATH = {"math", "displaymath", "equation", "align", "alignat", "flalign", "gather",
        "multline", "split", "aligned", "gathered", "array", "cases", "matrix"}
CLOSABLE = {"document", "abstract", "itemize", "enumerate", "description", "quote",
            "quotation", "center", "flushleft", "flushright", "figure", "figure*",
            "table", "table*", "tabular"} | MATH | {e + "*" for e in MATH}
TABLE = re.compile(r"\\begin\{tabular\}(\s*(?:\[[tbc]\]\s*)?)\{([lcr|\s]+)\}([\s\S]*?)\\end\{tabular\}")
TOKEN = re.compile(r"\\(?:verb\*?([^\w\s]).*?\1|[A-Za-z@]+|.)|\$\$?|\{|\}|[_&#%]")
GRAPHIC = re.compile(r"\\includegraphics\*?\s*(?:\[[^\]]*\]\s*)?\{\s*([^{}\\%#]+?)\s*\}")
INCLUDE_RE = re.compile(r"\\(include|input)\s*\{\s*([^{}\\%#]+?)\s*\}")


def chktex_findings(root, order, strict=False):
    tool = which("chktex")
    if not tool:
        return []
    findings = []
    for f in order:
        _, stdout, _ = run([tool, "-f", "%f:%l:%c:%k:%n:%m\n", "-q", "-I0",
                            "./" + f], cwd=root, timeout=5)
        for line in stdout.replace(r'\n', '\n').splitlines():
            m = re.match(r"^(.+?):(\d+):(\d+):([^:]+):(\d+):(.*)$", line)
            if m:
                _, row, col, kind, rule, msg = m.groups()
                rnum = int(rule)
                if not strict and (rnum in CHKTEX_NOISE_RULES or kind.lower() == "message"):
                    continue
                findings.append({"class": "chktex", "severity": "info" if kind.lower() == "message" else "warning",
                                 "file": f, "line": int(row), "column": int(col), "rule": rnum,
                                 "kind": kind, "message": msg.strip(), "source": "chktex"})
    return findings


def visible(text):
    """Mask comments and verbatim while retaining source offsets."""
    blocks = r"\\begin\{(" + "|".join(map(re.escape, VERB_ENVS)) + r")\}[\s\S]*?(?:\\end\{\1\}|$)"
    def blank(s):
        return re.sub(r"[^\n]", " ", s)
    text = re.sub(r"\\verb\*?([^\w\s]).*?\1", lambda m: blank(m[0]), text)
    text = re.sub(blocks, lambda m: blank(m[0]), text)
    return "\n".join((code := strip_comment(line)) + " " * (len(line) - len(code))
                     for line in text.split("\n"))


def graphic_target(target, bases, main_dir, engine):
    extensions = {".pdf", ".png", ".jpg", ".jpeg", ".mps"} if engine in {
        "pdflatex", "xelatex", "lualatex"} else {".eps", ".ps", ".pdf", ".png", ".jpg", ".jpeg"}
    raw = Path(target)
    if raw.is_absolute() or raw.drive or ".." in raw.parts:
        return None
    matches = set()
    exact = set()
    for base in bases:
        candidates = [(base, True)]
        for part in raw.parent.parts:
            candidates = [(p, same and p.name == part) for parent, same in candidates
                          if parent.is_dir() for p in parent.iterdir()
                          if p.is_dir() and not p.is_symlink() and p.name.casefold() == part.casefold()]
        for parent, same in candidates:
            for path in parent.iterdir():
                if not path.is_file() or path.is_symlink() or path.suffix.lower() not in extensions:
                    continue
                if same and (path.name == raw.name or
                             not raw.suffix and path.stem == raw.name and path.suffix in extensions):
                    exact.add(path)
                if path.stem.casefold() == raw.stem.casefold():
                    matches.add(path)
    if exact:
        return None
    same_name = {p for p in matches if p.name.casefold() == raw.name.casefold()}
    matches = same_name or matches
    if len(matches) == 1:
        return os.path.relpath(matches.pop(), main_dir).replace(os.sep, "/")


def _norm_tex_stem(s):
    return re.sub(r"(\D)0+(\d)", r"\1\2", s.casefold())


def tex_target(target, bases, main_dir, cmd):
    raw = Path(target)
    if raw.is_absolute() or raw.drive or ".." in raw.parts:
        return None
    for base in bases:
        cand = base / raw
        if cand.is_file() or (not raw.suffix and (base / (target + ".tex")).is_file()):
            return None
    raw_stem = _norm_tex_stem(raw.stem)
    matches = set()
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*.tex"):
            if path.is_file() and not path.is_symlink() and _norm_tex_stem(path.stem) == raw_stem:
                matches.add(path)
    if len(matches) == 1:
        rel = os.path.relpath(matches.pop(), main_dir).replace(os.sep, "/")
        if cmd == "include" and rel.endswith(".tex"):
            rel = rel[:-4]
        return rel
    return None


def repair_source(text, file, diagnostics, root, main, gpaths, packages, structural, engine):
    code = visible(text.replace('\r', ' '))
    start = re.search(r"\\begin\{document\}", code)
    if not start and file == main:
        return text, []
    edits = []
    reasons = set()

    def edit(a, b, new, reason):
        edits.append((a, b, new))
        reasons.add(reason)

    def line(pos):
        return code.count("\n", 0, pos) + 1

    if file == main and packages:
        match = re.search(r"\\usepackage(?:\s*\[[^\]]*\])?\s*\{[^{}]*\b(?:hyperref|cleveref)\b[^{}]*\}", code[:start.start()])
        pos = match.start() if match else start.start()
        edit(pos, pos, "".join("\\usepackage{" + pkg + "}\n" for pkg in packages),
             "load packages for compiler-identified commands and environments")

    main_dir = root / Path(main).parent
    bases = [main_dir, root] + [main_dir / Path(g) for g in gpaths
                         if not Path(g).is_absolute() and ".." not in Path(g).parts and "\\" not in g]
    file_d = [d for d in diagnostics if d.get("file") == file]
    missing = {d.get("line") for d in file_d if d["class"] == "missing_file"}
    path_edits = []
    for m in GRAPHIC.finditer(code):
        if line(m.start()) not in missing:
            continue
        target = graphic_target(m[1], bases, main_dir, engine)
        if target and target != m[1]:
            path_edits.append((m.start(1), m.end(1), target, "resolve unique local graphic path"))
    for m in INCLUDE_RE.finditer(code):
        if line(m.start()) not in missing:
            continue
        target = tex_target(m[2], [main_dir, root], main_dir, m[1])
        if target and target != m[2]:
            path_edits.append((m.start(2), m.end(2), target, "resolve unique local TeX include/input path"))
    edits.extend((a, b, new) for a, b, new, _ in path_edits)
    reasons.update(reason for *_, reason in path_edits)

    tables = list(TABLE.finditer(code))
    for table in tables:
        # Restrict row repairs to simple alignment: literal cell separators and no spans.
        # Other types of tables still benefit from structured diagnostics.
        body = table[3]
        cols = len(re.findall("[lcr]", table[2]))
        if not cols or re.search(r"\\(?:begin|end|multicolumn|omit|span|verb)\b", text[table.start(3):table.end(3)]):
            continue
        simple_table_rows(body, table.start(3), cols, table.end(2), edit)
        overfull = any(d["class"] == "overfull_box" and
                       line(table.start()) <= (d.get("line") or 0) <= line(table.end())
                       for d in file_d)
        safe_layout = not re.search(r"\\(?:footnote|verb|label|write|stepcounter|refstepcounter)\b", body)
        before = code[code.rfind("\n", 0, table.start()) + 1:table.start()]
        after = code[table.end():code.find("\n", table.end()) if "\n" in code[table.end():] else len(code)]
        if structural and overfull and not edits and safe_layout and not before.strip() and not after.strip():
            # Wrapped columns preserve declared alignment and every cell in source order.
            align = {"l": r"\raggedright", "c": r"\centering", "r": r"\raggedleft"}
            spec = "".join(">{" + align[c] + r"\arraybackslash}X" if c in align else c for c in table[2])
            edit(table.start(), table.start(3), r"\noindent\begin{tabularx}{\linewidth}" + table[1] + "{" + spec + "}",
                 "wrap overwide table to local linewidth")
            edit(table.end(3), table.end(), r"\end{tabularx}", "wrap overwide table to local linewidth")

    if structural:
        repair_structure(code, text, start, file_d, edit)
    repair_literals(code, text, start, file_d, edit)
    crlf = '\r\n' in text and '\n' not in text.replace('\r\n', '')
    for a, b, new in sorted(edits, reverse=True):
        if crlf:
            new = new.replace('\n', '\r\n')
        text = text[:a] + new + text[b:]
    return text, sorted(reasons)


def simple_table_rows(body, offset, cols, spec_end, edit):
    rows = []
    for row in re.finditer(r"(.*?)(?<!\\)\\\\(?:\[[^\]\n]*\])?|(.+)\Z", body, re.S):
        content = row[1] if row[1] is not None else row[2]
        content_start = row.start()
        content = re.sub(r"\\(?:hline|toprule|midrule|bottomrule)\b", lambda m: " " * len(m[0]), content)
        if not content.strip():
            continue
        # Ampersands inside formulas, groups and macro arguments need a TeX-aware author decision.
        if re.search(r"[{}$]|\\(?:\[|\(|tabularnewline|cr|cline|cmidrule|rowcolor|noalign)", content):
            return
        rows.append((content, content_start, len(re.findall(r"(?<!\\)&", content)) + 1))
    counts = [count for _, _, count in rows]
    if len(counts) >= 2 and min(counts) == max(counts) > cols:
        edit(spec_end, spec_end, "l" * (counts[0] - cols), "extend column spec to consistently wider rows")
    if cols not in counts:
        return
    for content, pos, count in rows:
        if count == cols + 1:
            amps = [m.start() for m in re.finditer(r"(?<!\\)&", content)]
            compact = [at for at in amps if re.fullmatch(r"[A-Z]&[A-Z]", content[at-1:at+2])]
            if len(compact) == 1 and all(at == compact[0] or content[at-1:at+2] == " & " for at in amps):
                at = offset + pos + compact[0]
                edit(at, at, "\\", "escape compact acronym ampersand in an overlong row")
            continue
        if count != cols - 1 or not re.fullmatch(r"[\w\s.&,+:%#()/-]+", content):
            continue
        gaps = list(re.finditer(r"(?<=[\w.)])[ \t]{2,}(?=[\w(])", content))
        if len(gaps) == 1:
            gap = gaps[0]
            edit(offset + pos + gap.start(), offset + pos + gap.end(), " & ",
                 "restore missing table separator at explicit spacing")


def repair_structure(code, text, start, diagnostics, edit):
    kinds = {d["class"] for d in diagnostics}
    if "brace" in kinds or "runaway" in kinds:
        # A one-line text argument followed by a blank line, command or EOF gives an explicit boundary.
        for m in re.finditer(r"(?m)^[ \t]*\\(?:textbf|textit|emph|section|subsection|paragraph)\{([^{}\\%$\n]+)$", code):
            following = code[m.end() + 1:].lstrip(" \t")
            if m[1].strip() and (not following or following.startswith(("\n", "\\"))):
                end = m.start(1) + len(m[1].rstrip())
                edit(end, end, "}", "close a single-line text argument")
                return
    if start is None or not kinds & {"env_mismatch", "no_end", "runaway", "brace"}:
        return
    stack = []
    for m in ENV.finditer(code, start.start()):
        action, name = m.groups()
        if action == "begin":
            stack.append(name)
        elif stack and stack[-1] == name:
            stack.pop()
        elif name == "document" and stack and stack[0] == "document" and all(e in CLOSABLE for e in stack):
            edit(m.start(), m.start(), "".join("\\end{" + e + "}\n" for e in reversed(stack[1:])),
                 "close open environments before end of document")
            return
        else:
            return
    if stack and stack[0] == "document" and all(e in CLOSABLE for e in stack):
        end = len(text)
        edit(end, end, "\n" + "".join("\\end{" + e + "}\n" for e in reversed(stack)), "close environments at EOF")


def repair_literals(code, text, start, diagnostics, edit):
    located = {}
    for d in diagnostics:
        if d.get("line"):
            located.setdefault(d["line"], []).append(d["message"])
    scopes, brace, math = [], 0, None
    beginning = start.end() if start else 0
    blocked = False
    # Numeric percentages before sentence punctuation, subject to the same scope checks as other literals.
    masked = list(code)
    for m in re.compile(r"(?m)(?<=\d)%(?=[.,;:!?][ \t]*\r?$)").finditer(text, beginning):
        prefix = code[code.rfind("\n", 0, m.start()) + 1:m.start()]
        if re.fullmatch(r"[ \t]*[^\W\d_][\w \t.,;:!?-]*\d", prefix):
            masked[m.start()] = "%"
    for m in TOKEN.finditer("".join(masked), beginning):
        token = m[0]
        env = ENV.match(code, m.start()) if token in (r"\begin", r"\end") else None
        if env:
            if token == r"\begin":
                scopes.append(env[2])
            elif scopes and scopes[-1] == env[2]:
                scopes.pop()
        elif token in ("$", "$$", r"\(", r"\[", r"\)", r"\]"):
            math = None if math == token else {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}.get(token, math)
        elif token == "{":
            brace += 1
        elif token == "}":
            brace = max(0, brace - 1)
        elif re.fullmatch(r"\\(?:def|[a-z]*command|[a-z]*environment|catcode|ExplSyntaxOn)", token, re.I):
            blocked = True
        elif token in "_&#%" and not (blocked or math or brace or any(e.rstrip("*") in MATH for e in scopes)):
            n = code.count("\n", 0, m.start()) + 1
            messages = located.get(n, [])
            in_table = any(e in {"tabular", "tabular*", "tabularx", "longtable"} for e in scopes)
            if token == "%":
                edit(m.start(), m.start(), "\\", "restore literal numeric percent before punctuation")
            elif ((token == "_" and any("Missing $" in msg for msg in messages)) or
                (token == "#" and any("macro parameter character" in msg for msg in messages)) or
                (token == "&" and not in_table and any("Misplaced alignment tab" in msg for msg in messages))):
                edit(m.start(), m.start(), "\\", "escape compiler-identified literal punctuation")
