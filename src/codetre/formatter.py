"""Formatter module: text output formatting for scan results."""

import os

from .patterns import LANG_MAP, IMPORT_PATTERNS
from .symbol import Symbol, FileResult
from .scanner import sg_json


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
        for m in sg_json(pat, lang, path):
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
