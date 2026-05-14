"""CLI for codetre."""

import argparse
import json
import os
import sys

from .scanner import check_sg, quiet as core_quiet, scan_path, scan_paths
from .formatter import DisplayConfig, DEFAULT_DISPLAY_CONFIG, format_result

VERSION = "0.3.3"


def main():
    parser = argparse.ArgumentParser(
        prog="codetre",
        description="Hierarchical code structure outline with call relationships.",
        epilog="Powered by ast-grep tree-sitter integration.",
    )
    parser.add_argument("path", nargs="*", default=["."],
                        help="File(s) or director(ies) to scan (default: current dir)")
    parser.add_argument("--json", action="store_true",
                        help="Output in JSON format")
    parser.add_argument("--exclude", action="append", default=[],
                        help="Glob pattern to exclude files (can be repeated)")
    parser.add_argument("--threads", type=int, default=0,
                        help="Number of worker threads (0 = auto, 1 = sequential)")
    parser.add_argument("--no-ignore", action="store_true",
                        help="Do not skip common directories (.git, __pycache__, node_modules, etc.)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress non-output messages")
    parser.add_argument("--version", action="store_true",
                        help="Show version and exit")
    parser.add_argument("--imports", choices=["show", "count", "hide"],
                        default=DEFAULT_DISPLAY_CONFIG.imports,
                        help="Display mode for import blocks (default: %(default)s)")
    parser.add_argument("--fields", choices=["show", "count", "hide"],
                        default=DEFAULT_DISPLAY_CONFIG.fields,
                        help="Display mode for field symbols inside containers (default: %(default)s)")
    parser.add_argument("--vars", choices=["show", "count", "hide"],
                        default=DEFAULT_DISPLAY_CONFIG.vars,
                        help="Display mode for variable/const symbols (default: %(default)s)")
    args = parser.parse_args()

    if args.version:
        print(f"codetre {VERSION}")
        sys.exit(0)

    err = check_sg()
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    if args.quiet:
        core_quiet()

    if len(args.path) == 1:
        results = scan_path(args.path[0], args.exclude, args.threads, args.no_ignore)
        base_dir = args.path[0] if os.path.isdir(args.path[0]) else os.path.dirname(args.path[0]) or "."
    else:
        results = scan_paths(args.path, args.exclude, args.threads, args.no_ignore)
        base_dir = "."

    if not results:
        if not args.quiet:
            paths_str = ", ".join(args.path)
            print(f"no symbols found in {paths_str}", file=sys.stderr)
        sys.exit(2)

    total_symbols = sum(len(r.symbols) for r in results)

    if args.json:
        items = []
        for r in results:
            rel = os.path.relpath(r.file, base_dir)
            items.append({
                "file": rel,
                "symbols": [
                    {"name": s.name, "kind": s.kind, "line_start": s.line_start, "line_end": s.line_end, "calls": s.calls}
                    for s in r.symbols
                ],
            })
        if len(items) == 1:
            print(json.dumps(items[0], ensure_ascii=False))
        else:
            print(json.dumps(items, ensure_ascii=False))
    else:
        display_config = DisplayConfig(
            imports=args.imports,
            fields=args.fields,
            vars=args.vars,
        )
        print("# format: name:start,count  -> [file-local ref, ...]")
        print()
        for i, r in enumerate(results):
            if i > 0:
                print()
            print(format_result(r, base_dir, display_config))

        # Summary line (stderr so it doesn't pollute piped/redirected output)
        if not args.quiet:
            file_word = "file" if len(results) == 1 else "files"
            sym_word = "symbol" if total_symbols == 1 else "symbols"
            print(f"# {len(results)} {file_word}, {total_symbols} {sym_word}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
