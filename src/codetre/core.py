"""Core engine: runs ast-grep to extract symbols and call relationships."""

import subprocess
import json
import os
import shutil
from pathlib import PurePath
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .patterns import LANG_MAP, DEF_PATTERNS, CALL_PATTERNS

SG_TIMEOUT = 30


def check_sg() -> str | None:
    if shutil.which("sg"):
        return None
    return (
        "error: ast-grep (sg) not found\n"
        "\n"
        "  Install it:\n"
        "    npm install -g @ast-grep/cli\n"
        "    # or: scoop install sg        (Windows)\n"
        "    # or: brew install ast-grep   (macOS)\n"
        "    # or: cargo install ast-grep  (from source)\n"
        "\n"
        "  See: https://ast-grep.github.io"
    )


def _sg_json(pattern: str, lang: str, filepath: str):
    try:
        r = subprocess.run(
            ["sg", "run", "--pattern", pattern, "--lang", lang, "--json=compact", filepath],
            capture_output=True, encoding="utf-8", timeout=SG_TIMEOUT,
        )
    except FileNotFoundError:
        return []
    except subprocess.TimeoutExpired:
        return []

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


@dataclass
class Symbol:
    name: str
    kind: str
    ls: int
    le: int
    calls: list[str] = field(default_factory=list)


@dataclass
class FileResult:
    file: str
    symbols: list[Symbol]


def scan_file(path: str) -> FileResult | None:
    ext = os.path.splitext(path)[1]
    lang = LANG_MAP.get(ext)
    if not lang or not os.path.isfile(path):
        return None

    raw = []
    for pat, kind in DEF_PATTERNS.get(lang, []):
        for m in _sg_json(pat, lang, path):
            raw.append({
                "name": m["metaVariables"]["single"]["NAME"]["text"],
                "kind": kind,
                "ls": m["range"]["start"]["line"] + 1,
                "le": m["range"]["end"]["line"] + 1,
            })

    if not raw:
        return None

    seen: set[tuple[str, str, int]] = set()
    raw = [s for s in raw
           if not ((s["name"], s["kind"], s["ls"]) in seen or seen.add((s["name"], s["kind"], s["ls"])))]

    symbols = [Symbol(name=s["name"], kind=s["kind"], ls=s["ls"], le=s["le"]) for s in raw]
    name_map: dict[str, list[Symbol]] = {}
    for s in symbols:
        name_map.setdefault(s.name, []).append(s)

    all_calls = _extract_call_names(CALL_PATTERNS.get(lang, []), lang, path)

    for s in symbols:
        body_calls: set[str] = set()
        kids = [x for x in symbols if x is not s and x.ls > s.ls and x.le <= s.le]
        for callee_name, call_line in all_calls:
            if call_line <= s.ls or call_line > s.le:
                continue
            if any(k.ls < call_line <= k.le for k in kids):
                continue
            candidates = name_map.get(callee_name, [])
            for c in candidates:
                if c.ls == s.ls and c.name == s.name:
                    continue
                body_calls.add(callee_name)
        s.calls = sorted(body_calls)

    return FileResult(file=path, symbols=symbols)


def scan_dir(
    dirpath: str,
    exclude_patterns: list[str] | None = None,
    threads: int = 0,
) -> list[FileResult]:
    exclude = exclude_patterns or []
    files: list[str] = []
    for root, dirs, fnames in os.walk(dirpath):
        dirs.sort()
        for fname in sorted(fnames):
            path = os.path.join(root, fname)
            ext = os.path.splitext(path)[1]
            if ext not in LANG_MAP:
                continue
            rel = os.path.relpath(path, dirpath)
            if any(PurePath(rel).match(pat) for pat in exclude):
                continue
            files.append(path)

    if not files:
        return []

    if threads == 1:
        results: list[FileResult] = []
        for f in files:
            r = scan_file(f)
            if r:
                results.append(r)
        return results

    max_workers = threads if threads > 1 else None
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {pool.submit(scan_file, f): f for f in files}
        for fut in as_completed(fut_map):
            try:
                r = fut.result()
                if r:
                    results.append(r)
            except Exception:
                pass

    results.sort(key=lambda r: r.file)
    return results


def scan_path(
    path: str,
    exclude_patterns: list[str] | None = None,
    threads: int = 0,
) -> list[FileResult]:
    if os.path.isfile(path):
        r = scan_file(path)
        return [r] if r else []
    if os.path.isdir(path):
        return scan_dir(path, exclude_patterns, threads)
    return []


def format_result(result: FileResult, base_dir: str = "") -> str:
    rel = os.path.relpath(result.file, base_dir) if base_dir else result.file
    symbols = result.symbols
    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]
    funcs = [s for s in symbols if s.kind == "func"]

    lines = [f"file: {rel}"]
    for c in containers:
        ccall = f"  -> call[{', '.join(c.calls)}]" if c.calls else ""
        lines.append(f"  {c.kind} {c.name}:{c.ls}~{c.le}{ccall}")
        kids = [f for f in funcs if f.ls > c.ls and f.le <= c.le]
        for k in kids:
            kcall = f"  -> call[{', '.join(k.calls)}]" if k.calls else ""
            lines.append(f"    func {k.name}:{k.ls}~{k.le}{kcall}")

    top = [f for f in funcs
           if not any(f.ls >= c.ls and f.le <= c.le for c in containers)]
    for f in top:
        fcall = f"  -> call[{', '.join(f.calls)}]" if f.calls else ""
        lines.append(f"  func {f.name}:{f.ls}~{f.le}{fcall}")

    return "\n".join(lines)


def format_json(result: FileResult, base_dir: str = "") -> str:
    rel = os.path.relpath(result.file, base_dir) if base_dir else result.file
    return json.dumps({
        "file": rel,
        "symbols": [
            {
                "name": s.name,
                "kind": s.kind,
                "line_start": s.ls,
                "line_end": s.le,
                "calls": s.calls,
            }
            for s in result.symbols
        ],
    }, ensure_ascii=False)
