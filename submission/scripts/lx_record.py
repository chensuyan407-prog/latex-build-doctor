#!/usr/bin/env python3
"""Inspect or record diffs between work/orig and work/src into work/changes.json without manual line/escaping errors.

  python3 lx_record.py --work /app/work
      -> prints every undocumented diff hunk (file, line, from, to).

  python3 lx_record.py --work /app/work --auto --reason "fixed compile errors" [--fixes E001] [--type math] [--accept-numbers] [--accept-keys]
      -> appends change records for all currently undocumented hunks to work/changes.json.

  python3 lx_record.py --work /app/work --confirm "missing ref tab:x" --where "results.tex:26"
      -> appends a needs_confirmation item.

  python3 lx_record.py --work /app/work --set-field "key=value"
      -> sets a contract field override in work/changes.json -> fields (JSON value or string).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lx_build import audit_changes, diff_project
from lx_common import load_json, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--auto", action="store_true", help="record all undocumented diff hunks automatically")
    ap.add_argument("--reason", default="", help="reason for --auto records")
    ap.add_argument("--fixes", default="", help="diagnostic id or task item")
    ap.add_argument("--type", default="fix", help="change category (package/math/table/citation/template/font/structure/fix)")
    ap.add_argument("--file", help="filter --auto to this relative file path")
    ap.add_argument("--accept-numbers", action="store_true")
    ap.add_argument("--accept-keys", action="store_true")
    ap.add_argument("--confirm", help="append a needs_confirmation item")
    ap.add_argument("--where", default="")
    ap.add_argument("--set-field", action="append", default=[], help="set changes.json fields[k]=v (can repeat)")
    a = ap.parse_args()

    work = os.path.abspath(a.work)
    orig, src = os.path.join(work, "orig"), os.path.join(work, "src")
    ch_path = os.path.join(work, "changes.json")
    data = load_json(ch_path, None)
    if not isinstance(data, dict):
        data = {"changes": [], "requirements": [], "needs_confirmation": [], "notes": [], "fields": {}}
    recs = data.setdefault("changes", [])

    if a.confirm:
        nc = data.setdefault("needs_confirmation", [])
        entry = {"item": a.confirm, "where": a.where} if a.where else {"item": a.confirm}
        if entry not in nc:
            nc.append(entry)

    PROTECTED_FIELDS = {"case_id", "status", "skill", "artifacts", "build", "diagnostics_summary", "sources", "environment"}
    for kv in a.set_field:
        if "=" not in kv:
            print("ERROR --set-field must be key=value, got %r" % kv)
            return 2
        k, raw = kv.split("=", 1)
        k = k.strip()
        if k in PROTECTED_FIELDS:
            print("ERROR cannot overwrite protected core field %r" % k)
            return 2
        try:
            val = json.loads(raw)
        except ValueError:
            val = raw
        data.setdefault("fields", {})[k] = {"value": val}

    hunks, _ = diff_project(orig, src) if os.path.isdir(orig) and os.path.isdir(src) else ([], "")
    audit_changes(hunks, recs)
    undoc = [h for h in hunks if not h.get("records") and (not a.file or h["file"] == a.file.replace("\\", "/"))]

    if a.auto:
        if not a.reason:
            print("ERROR --auto requires --reason")
            return 2
        added = 0
        for h in undoc:
            rec = {"file": h["file"], "line": h.get("new_start") or 1, "from": h["old"], "to": h["new"], "reason": a.reason, "type": a.type}
            if h["kind"] in ("new_file", "binary_or_other"):
                rec["type"] = "new_file"
                rec["from"] = ""
                rec["to"] = ""
            if a.fixes:
                rec["fixes"] = a.fixes
            if a.accept_numbers:
                rec["accept_numbers"] = True
            if a.accept_keys:
                rec["accept_keys"] = True
            recs.append(rec)
            added += 1
        write_json(ch_path, data)
        print("Recorded %d hunk(s) into %s (total records: %d)." % (added, ch_path, len(recs)))
        return 0

    if a.confirm or a.set_field:
        write_json(ch_path, data)
        print("Updated %s." % ch_path)

    if not undoc:
        print("All %d diff hunk(s) are documented." % len(hunks))
        return 0
    print("Undocumented diff hunks (%d):" % len(undoc))
    for h in undoc:
        print("  %s %s:%s (%s)" % (h["id"], h["file"], h.get("new_start"), h["kind"]))
        if h["old"]:
            print("    from: %s" % repr(h["old"][:120]))
        if h["new"]:
            print("    to:   %s" % repr(h["new"][:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
