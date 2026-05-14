"""CLI for codetre."""

import argparse
import json
import os
import sys

from .core import check_sg, quiet as core_quiet, scan_path, format_result

VERSION = "0.2.1"


def main():
    err = check_sg()
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="codetre",
        description="Hierarchical code structure outline with call relationships.",
        epilog="Powered by ast-grep tree-sitter integration.",
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="File or directory to scan (default: current dir)")
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
    args = parser.parse_args()

    if args.version:
        print(f"codetre {VERSION}")
        sys.exit(0)

    if args.quiet:
        core_quiet()

    results = scan_path(args.path, args.exclude, args.threads, args.no_ignore)

    if not results:
        if not args.quiet:
            print(f"no symbols found in {args.path}", file=sys.stderr)
        sys.exit(2)

    base_dir = args.path if os.path.isdir(args.path) else os.path.dirname(args.path) or "."

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
        print("# format: name:start,count  -> [file-local ref, ...]")
        print()
        for i, r in enumerate(results):
            if i > 0:
                print()
            print(format_result(r, base_dir))

    sys.exit(0)


if __name__ == "__main__":
    main()
