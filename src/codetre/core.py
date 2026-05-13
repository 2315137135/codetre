"""Core engine: runs ast-grep to extract symbols and call relationships."""

import subprocess
import json
import os

from .patterns import LANG_MAP, DEF_PATTERNS, CALL_PATTERNS


def _sg_json(pattern: str, lang: str, filepath: str):
    r = subprocess.run(
        ["sg", "run", "--pattern", pattern, "--lang", lang, "--json", filepath],
        capture_output=True, encoding="utf-8",
    )
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


def _extract_call_names(matchers, lang: str, path: str):
    calls = []
    for pat, extract_fn in matchers:
        for m in _sg_json(pat, lang, path):
            line = m["range"]["start"]["line"] + 1
            name = extract_fn(m)
            if name:
                calls.append((name, line))
    return calls


def scan_file(path: str) -> dict | None:
    ext = os.path.splitext(path)[1]
    lang = LANG_MAP.get(ext)
    if not lang or not os.path.isfile(path):
        return None

    symbols = []
    for pat, kind in DEF_PATTERNS.get(lang, []):
        for m in _sg_json(pat, lang, path):
            symbols.append({
                "name": m["metaVariables"]["single"]["NAME"]["text"],
                "kind": kind,
                "ls": m["range"]["start"]["line"] + 1,
                "le": m["range"]["end"]["line"] + 1,
            })

    if not symbols:
        return None

    seen = set()
    symbols = [s for s in symbols
               if not ((s["name"], s["kind"], s["ls"]) in seen or seen.add((s["name"], s["kind"], s["ls"])))]

    name_map = {}
    for s in symbols:
        name_map.setdefault(s["name"], []).append(s)

    all_calls = _extract_call_names(CALL_PATTERNS.get(lang, []), lang, path)

    for s in symbols:
        body_calls = set()
        kids = [x for x in symbols if x != s and x["ls"] > s["ls"] and x["le"] <= s["le"]]
        for callee_name, call_line in all_calls:
            if call_line <= s["ls"] or call_line > s["le"]:
                continue
            if any(k["ls"] < call_line <= k["le"] for k in kids):
                continue
            candidates = name_map.get(callee_name, [])
            for c in candidates:
                if c["ls"] == s["ls"] and c["name"] == s["name"]:
                    continue
                body_calls.add(callee_name)
        s["calls"] = sorted(body_calls)

    return {"file": path, "symbols": symbols}


def format_result(result: dict, base_dir: str = "") -> str:
    rel = os.path.relpath(result["file"], base_dir)
    symbols = result["symbols"]
    containers = [s for s in symbols if s["kind"] in ("class", "struct", "interface", "impl")]
    funcs = [s for s in symbols if s["kind"] == "func"]

    lines = [f"file: {rel}"]
    for c in containers:
        ccall = f"  -> call[{', '.join(c['calls'])}]" if c["calls"] else ""
        lines.append(f"  {c['kind']} {c['name']}:{c['ls']}~{c['le']}{ccall}")
        kids = [f for f in funcs if f["ls"] > c["ls"] and f["le"] <= c["le"]]
        for k in kids:
            kcall = f"  -> call[{', '.join(k['calls'])}]" if k["calls"] else ""
            lines.append(f"    func {k['name']}:{k['ls']}~{k['le']}{kcall}")

    top = [f for f in funcs
           if not any(f["ls"] >= c["ls"] and f["le"] <= c["le"] for c in containers)]
    for f in top:
        fcall = f"  -> call[{', '.join(f['calls'])}]" if f["calls"] else ""
        lines.append(f"  func {f['name']}:{f['ls']}~{f['le']}{fcall}")

    return "\n".join(lines)


def scan_dir(dirpath: str):
    results = []
    for root, dirs, files in os.walk(dirpath):
        dirs.sort()
        for f in sorted(files):
            path = os.path.join(root, f)
            result = scan_file(path)
            if result:
                results.append(result)
    return results
