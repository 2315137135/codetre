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

from .patterns import LANG_MAP, DEF_PATTERNS, CALL_PATTERNS, KIND_DEFS, IMPORT_PATTERNS

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
    result = {}
    for base in {os.getcwd(), dirpath}:
        path = os.path.join(base, '.gitignore')
        if os.path.isfile(path) and base not in result:
            try:
                with open(path, encoding='utf-8') as f:
                    result[base] = pathspec.PathSpec.from_lines('gitwildmatch', f)
            except Exception:
                pass
    return result if result else None


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


def _run_sg(args: list[str]) -> list[dict]:
    """Run an ast-grep command and return parsed JSON results."""
    try:
        r = subprocess.run(
            ["sg", *args],
            capture_output=True, encoding="utf-8", timeout=SG_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


def _sg_json(pattern: str, lang: str, filepath: str):
    """Match definitions or imports via sg run --pattern."""
    return _run_sg(["run", "--pattern", pattern, "--lang", lang, "--json=compact", filepath])


def _sg_kind_json(kind_name: str, lang: str, filepath: str):
    """Match by AST node kind via sg scan --inline-rules."""
    rule = f"id: {kind_name}\nlanguage: {lang}\nrule:\n  kind: {kind_name}"
    return _run_sg(["scan", "--inline-rules", rule, "--json=compact", filepath])


def _extract_kind_name(text: str, kind: str) -> str:
    if kind in ('method_definition', 'function_declaration'):
        name = text.split('(')[0].strip()
        return name.split()[-1] if name.split() else name
    if kind == 'public_field_definition':
        name_part = text.split(':')[0].strip()
        return name_part.split()[-1] if name_part.split() else name_part
    if kind == 'field_definition':
        return text.split('=')[0].strip()
    if kind in ('lexical_declaration', 'variable_declaration'):
        rest = text.split(None, 1)[1] if ' ' in text else text
        name = rest.split('=')[0].split(':')[0].strip()
        return name
    return text


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


def _extract_raw_symbols(path: str) -> tuple[str, list[dict]] | None:
    """Detect language and extract raw symbol dicts via pattern & kind matchers.

    Returns (lang, raw_symbols) on success, or None if the file is not scannable
    or contains no symbols.
    """
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

    for kind_name, sym_kind in KIND_DEFS.get(lang, []):
        for m in _sg_kind_json(kind_name, lang, path):
            raw.append({
                "name": _extract_kind_name(m["text"], kind_name),
                "kind": sym_kind,
                "line_start": m["range"]["start"]["line"] + 1,
                "line_end": m["range"]["end"]["line"] + 1,
            })

    if not raw:
        return None
    return lang, raw


def _dedup_raw(raw: list[dict]) -> list[dict]:
    """Remove duplicate symbol entries (same name, kind, start line)."""
    seen: set[tuple[str, str, int]] = set()
    result = []
    for s in raw:
        key = (s["name"], s["kind"], s["line_start"])
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _assign_calls(symbols: list[Symbol], lang: str, path: str) -> None:
    """Extract all call sites and assign callee names to each symbol in place."""
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


def _build_container_hierarchy(symbols: list[Symbol]) -> None:
    """Assign child symbols (funcs, fields) to container symbols in place."""
    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]
    for c in containers:
        c.children = [s for s in symbols
                      if s is not c and s.line_start > c.line_start and s.line_end <= c.line_end
                      and s.kind in ("func", "field")]


def _filter_inner_vars(symbols: list[Symbol], lang: str, path: str) -> list[Symbol]:
    """Remove vars nested inside functions or Python __main__ blocks."""
    funcs = [s for s in symbols if s.kind == "func"]

    inside_funcs: set[int] = set()
    for f in funcs:
        for s in symbols:
            if (s is not f and s.kind in ("func", "field", "var")
                    and s.line_start >= f.line_start and s.line_end <= f.line_end
                    and (s.line_start > f.line_start or s.line_end < f.line_end)):
                inside_funcs.add(id(s))

    # Detect if __name__ == "__main__" blocks — vars inside them are not module constants
    inside_main: set[int] = set()
    if lang == 'python':
        for m in _sg_json('if __name__ == $VAL: $$$BODY', lang, path):
            start = m["range"]["start"]["line"] + 1
            end = m["range"]["end"]["line"] + 1
            for s in symbols:
                if s.kind == "var" and start <= s.line_start <= end:
                    inside_main.add(id(s))

    return [s for s in symbols
            if s.kind in ("class", "struct", "interface", "impl", "func", "field")
            or (s.kind == "var" and id(s) not in inside_funcs and id(s) not in inside_main)]


def scan_file(path: str) -> FileResult | None:
    extracted = _extract_raw_symbols(path)
    if extracted is None:
        return None
    lang, raw = extracted

    raw = _dedup_raw(raw)
    symbols = [Symbol(name=s["name"], kind=s["kind"], line_start=s["line_start"], line_end=s["line_end"])
               for s in raw]

    _assign_calls(symbols, lang, path)
    _build_container_hierarchy(symbols)
    symbols = _filter_inner_vars(symbols, lang, path)

    return FileResult(file=path, symbols=symbols)


def scan_dir(
    dirpath: str,
    exclude_patterns: list[str] | None = None,
    threads: int = 0,
    no_ignore: bool = False,
) -> list[FileResult]:
    exclude = exclude_patterns or []
    ignore_map = _load_gitignore(dirpath) if not no_ignore else None
    files: list[str] = []
    for root, dirs, fnames in os.walk(dirpath):
        dirs.sort()

        if not no_ignore:
            dirs[:] = [d for d in dirs if d not in _DEFAULT_IGNORE_DIRS]

        if not no_ignore and ignore_map:
            for base, spec in ignore_map.items():
                rel_base = os.path.relpath(root, base).replace("\\", "/")
                dirs[:] = [d for d in dirs
                           if not spec.match_file(os.path.join(rel_base, d).replace("\\", "/") + "/_")]

        if exclude:
            dirs[:] = [d for d in dirs
                       if not any(PurePath(d).match(pat) for pat in exclude)]

        for fname in sorted(fnames):
            path = os.path.join(root, fname)
            ext = os.path.splitext(path)[1]
            if ext not in LANG_MAP:
                continue
            # Skip gitignored files
            if not no_ignore and ignore_map:
                ignored = False
                for base, spec in ignore_map.items():
                    rel = os.path.relpath(path, base).replace("\\", "/")
                    if spec.match_file(rel):
                        ignored = True
                        break
                if ignored:
                    continue
            # Skip files matching --exclude patterns
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


def _count_lines(filepath: str) -> int:
    """Count total lines in a file."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _symbol_line(s: Symbol) -> str:
    """Format a single symbol line: kind name:line_start,line_count [-> [callee, ...]]"""
    line_len = s.line_end - s.line_start + 1
    if s.kind in ("var", "field"):
        part = f"{s.kind} {s.name}:{s.line_start}"
    else:
        part = f"{s.kind} {s.name}:{s.line_start},{line_len}"
    if s.calls:
        part += f" -> [{', '.join(s.calls)}]"
    return part


def _extract_import_lines(path: str, lang: str) -> list[str]:
    """Extract raw import lines from source file, preserving original text."""
    import_patterns = IMPORT_PATTERNS.get(lang, [])
    if not import_patterns:
        return []

    ranges = []
    for pat, _ in import_patterns:
        for m in _sg_json(pat, lang, path):
            start_line = m["range"]["start"]["line"] + 1
            end_line = m["range"]["end"]["line"] + 1
            ranges.append((start_line, end_line))
    if not ranges:
        return []

    ranges.sort()
    merged = []
    for s, e in ranges:
        if not merged:
            merged.append((s, e))
        else:
            last_s, last_e = merged[-1]
            if s <= last_e + 1:
                merged[-1] = (last_s, max(last_e, e))
            else:
                merged.append((s, e))

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.readlines()
        raw_lines = []
        for s, e in merged:
            for i in range(s - 1, e):
                if i < len(source):
                    raw_lines.append(source[i].rstrip("\n\r"))
        return raw_lines
    except Exception:
        return []


def format_result(result: FileResult, base_dir: str = "") -> str:
    rel = os.path.relpath(result.file, base_dir) if base_dir else result.file
    total_lines = _count_lines(result.file)
    symbols = result.symbols
    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]
    funcs = [s for s in symbols if s.kind == "func"]
    vars = [s for s in symbols if s.kind == "var"]

    lines = [f"file: {rel},{total_lines}"]

    # Raw import block display (capped at 12 lines)
    ext = os.path.splitext(result.file)[1]
    lang = LANG_MAP.get(ext)
    if lang:
        raw_imports = _extract_import_lines(result.file, lang)
        if raw_imports:
            shown = raw_imports[:12]
            hidden = len(raw_imports) - 12
            for line in shown:
                lines.append(f"  {line}")
            if hidden > 0:
                lines.append(f"  ... ({hidden} more import lines)")
            lines.append("")

    for c in containers:
        lines.append(f"  {_symbol_line(c)}")
        for k in c.children:
            lines.append(f"    {_symbol_line(k)}")

    children_ids = set(id(s) for c in containers for s in c.children)
    top = [s for s in symbols
           if s.kind in ("func", "var") and id(s) not in children_ids and s not in containers]

    for s in top:
        lines.append(f"  {_symbol_line(s)}")

    return "\n".join(lines)
