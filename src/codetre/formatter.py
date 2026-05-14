"""Formatter module: text output formatting for scan results."""

import os
from dataclasses import dataclass

from .patterns import LANG_MAP, IMPORT_PATTERNS
from .symbol import Symbol, FileResult
from .scanner import sg_json


@dataclass
class DisplayConfig:
    """Control display granularity for symbol categories.

    Each field accepts one of:
      "show"   — fully expand (current default behaviour)
      "count"  — show a summary line:  imports(N) / fields(N) / vars(N)
      "hide"   — omit entirely
    """
    imports: str = "show"
    fields: str = "show"
    vars: str = "show"


# Module-level default — tune here to change default behaviour project-wide.
DEFAULT_DISPLAY_CONFIG = DisplayConfig()


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


def format_result(
    result: FileResult,
    base_dir: str = "",
    config: DisplayConfig | None = None,
) -> str:
    config = config or DEFAULT_DISPLAY_CONFIG
    rel = os.path.relpath(result.file, base_dir) if base_dir else result.file
    total_lines = _count_lines(result.file)
    symbols = result.symbols
    containers = [s for s in symbols if s.kind in ("class", "struct", "interface", "impl")]

    lines = [f"file: {rel},{total_lines}"]
    ext = os.path.splitext(result.file)[1]
    lang = LANG_MAP.get(ext)

    # ---- Imports ----
    if config.imports != "hide" and lang:
        raw_imports = _extract_import_lines(result.file, lang)
        if raw_imports:
            if config.imports == "show":
                shown = raw_imports[:12]
                hidden = len(raw_imports) - 12
                for line in shown:
                    lines.append(f"  {line}")
                if hidden > 0:
                    lines.append(f"  ... ({hidden} more import lines)")
            else:  # count
                lines.append(f"  imports({len(raw_imports)})")
            lines.append("")

    # ---- Containers (class / struct / interface / impl) ----
    for c in containers:
        lines.append(f"  {_symbol_line(c)}")
        child_fields = [k for k in c.children if k.kind == "field"]
        child_others = [k for k in c.children if k.kind != "field"]

        for k in child_others:
            lines.append(f"    {_symbol_line(k)}")

        if child_fields:
            if config.fields == "show":
                for k in child_fields:
                    lines.append(f"    {_symbol_line(k)}")
            elif config.fields == "count":
                lines.append(f"    fields({len(child_fields)})")
            # hide: skip

    # ---- Top-level symbols ----
    children_ids = set(id(s) for c in containers for s in c.children)
    top = [s for s in symbols
           if s.kind in ("func", "var") and id(s) not in children_ids and s not in containers]

    top_funcs = [s for s in top if s.kind == "func"]
    top_vars = [s for s in top if s.kind == "var"]

    for s in top_funcs:
        lines.append(f"  {_symbol_line(s)}")

    if top_vars:
        if config.vars == "show":
            for s in top_vars:
                lines.append(f"  {_symbol_line(s)}")
        elif config.vars == "count":
            lines.append(f"  vars({len(top_vars)})")
        # hide: skip

    return "\n".join(lines)
