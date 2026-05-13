"""Core engine: runs ast-grep to extract symbols and call relationships."""

import subprocess
import json
import os
import shutil
import sys
from pathlib import PurePath
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

try:
    import pathspec
except ImportError:
    pathspec = None

from .patterns import LANG_MAP, DEF_PATTERNS, CALL_PATTERNS

SG_TIMEOUT = 30

_DEFAULT_IGNORE_DIRS = frozenset({
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.tox', '.egg-info', '.mypy_cache', '.pytest_cache',
    'dist', 'build', 'target', '.idea', '.vscode',
})

_WARN_ENABLED = True


def quiet():
    global _WARN_ENABLED
    _WARN_ENABLED = False


def _warn(msg: str):
    if _WARN_ENABLED:
        print(f"warning: {msg}", file=sys.stderr)


def _load_gitignore(dirpath: str):
    if not pathspec:
        return None
    path = os.path.join(dirpath, '.gitignore')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return pathspec.PathSpec.from_lines('gitwildmatch', f)
    except Exception:
        return None


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
    line_start: int
    line_end: int
    calls: list[str] = field(default_factory=list)
    children: list["Symbol"] = field(default_factory=list)


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
                "line_start": m["range"]["start"]["line"] + 1,
                "line_end": m["range"]["end"]["line"] + 1,
            })

    if not raw:
        return None

    seen: set[tuple[str, str, int]] = set()
    raw = [s for s in raw
           if not ((s["name"], s["kind"], s["line_start"]) in seen or seen.add((s["name"], s["kind"], s["line_start"])))]

    symbols = [Symbol(name=s["name"], kind=s["kind"], line_start=s["line_start"], line_end=s["line_end"])
               for s in raw]
    name_map: dict[str, list[Symbol]] = {}
    for s in symbols:
        name_map.setdefault(s.name, []).append(s)

    all_calls = _extract_call_names(CALL_PATTERNS.get(lang, []), lang, path)

    for s in symbols:
        body_calls: set[str] = set()
        kids = [x for x in symbols if x is not s and x.line_start > s.line_start and x.line_end <= s.line_end]
        for callee_name, call_line in all_calls:
            if call_line <= s.line_start or call_line > s.line_end:
                continue
            if any(k.line_start < call_line <= k.line_end for k in kids):
                continue
            candidates = name_map.get(callee_name, [])
            for c in candidates:
                if c.line_start == s.line_start and c.name == s.name:
                    continue
                body_calls.add(callee_name)
        s.calls = sorted(body_calls)

    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]
    funcs = [s for s in symbols if s.kind == "func"]
    for c in containers:
        c.children = [f for f in funcs if f.line_start > c.line_start and f.line_end <= c.line_end]

    return FileResult(file=path, symbols=symbols)


def scan_dir(
    dirpath: str,
    exclude_patterns: list[str] | None = None,
    threads: int = 0,
    no_ignore: bool = False,
) -> list[FileResult]:
    exclude = exclude_patterns or []
    ignore_spec = _load_gitignore(dirpath) if not no_ignore else None
    files: list[str] = []
    for root, dirs, fnames in os.walk(dirpath):
        dirs.sort()

        if not no_ignore:
            dirs[:] = [d for d in dirs if d not in _DEFAULT_IGNORE_DIRS]

        if not no_ignore and ignore_spec:
            dirs[:] = [d for d in dirs
                       if not ignore_spec.match_file(
                           os.path.relpath(os.path.join(root, d), dirpath).replace("\\", "/") + "/_")]

        if exclude:
            dirs[:] = [d for d in dirs
                       if not any(PurePath(d).match(pat) for pat in exclude)]

        for fname in sorted(fnames):
            path = os.path.join(root, fname)
            ext = os.path.splitext(path)[1]
            if ext not in LANG_MAP:
                continue
            if not no_ignore and ignore_spec:
                rel = os.path.relpath(path, dirpath).replace("\\", "/")
                if ignore_spec.match_file(rel):
                    continue
            if exclude:
                rel = os.path.relpath(path, dirpath).replace("\\", "/")
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
            else:
                _warn(f"no symbols found in {f}")
        return results

    max_workers = threads if threads > 1 else None
    results: list[FileResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {pool.submit(scan_file, f): f for f in files}
        for fut in as_completed(fut_map):
            try:
                r = fut.result()
                if r:
                    results.append(r)
                else:
                    _warn(f"no symbols found in {fut_map[fut]}")
            except Exception as e:
                _warn(f"failed to scan {fut_map[fut]}: {e}")

    results.sort(key=lambda r: r.file)
    return results


def scan_path(
    path: str,
    exclude_patterns: list[str] | None = None,
    threads: int = 0,
    no_ignore: bool = False,
) -> list[FileResult]:
    if os.path.isfile(path):
        r = scan_file(path)
        return [r] if r else []
    if os.path.isdir(path):
        return scan_dir(path, exclude_patterns, threads, no_ignore)
    return []


def format_result(result: FileResult, base_dir: str = "") -> str:
    rel = os.path.relpath(result.file, base_dir) if base_dir else result.file
    symbols = result.symbols
    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]
    funcs = [s for s in symbols if s.kind == "func"]

    lines = [f"file: {rel}"]
    for c in containers:
        ccall = f"  -> call[{', '.join(c.calls)}]" if c.calls else ""
        lines.append(f"  {c.kind} {c.name}:{c.line_start}~{c.line_end}{ccall}")
        for k in c.children:
            kcall = f"  -> call[{', '.join(k.calls)}]" if k.calls else ""
            lines.append(f"    func {k.name}:{k.line_start}~{k.line_end}{kcall}")

    funcs_inside = set(id(f) for c in containers for f in c.children)
    top = [f for f in funcs if id(f) not in funcs_inside]

    for f in top:
        fcall = f"  -> call[{', '.join(f.calls)}]" if f.calls else ""
        lines.append(f"  func {f.name}:{f.line_start}~{f.line_end}{fcall}")

    return "\n".join(lines)
