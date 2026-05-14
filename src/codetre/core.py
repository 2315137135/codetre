"""Core engine: re-exports from submodules for backward compatibility."""

from .symbol import Symbol, FileResult
from .scanner import (
    SG_TIMEOUT, _DEFAULT_IGNORE_DIRS, _WARN_ENABLED,
    quiet, _warn, check_sg, _load_gitignore,
    _run_sg, sg_json, _sg_kind_json,
    _extract_kind_name, _extract_call_names,
    _extract_raw_symbols, _dedup_raw, _assign_calls,
    _build_container_hierarchy, _filter_inner_vars,
    scan_file, scan_dir, scan_path,
)
from .formatter import (
    _count_lines, _symbol_line, _extract_import_lines,
    DisplayConfig, DEFAULT_DISPLAY_CONFIG,
    format_result,
)
