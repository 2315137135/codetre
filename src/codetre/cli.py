"""CLI for codetre."""

import argparse
import os
import sys

from .core import scan_file, scan_dir, format_result


def main():
    parser = argparse.ArgumentParser(
        prog="codetre",
        description="Hierarchical code structure outline with call relationships.",
        epilog="Powered by ast-grep tree-sitter integration.",
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="File or directory to scan (default: current dir)")
    args = parser.parse_args()

    path = args.path

    try:
        if os.path.isfile(path):
            result = scan_file(path)
            if result:
                print(format_result(result, os.path.dirname(path)))
            else:
                print(f"no symbols found in {path}", file=sys.stderr)
                sys.exit(1)
        elif os.path.isdir(path):
            results = scan_dir(path)
            if not results:
                print(f"no supported source files found in {path}", file=sys.stderr)
                sys.exit(1)
            for r in results:
                print(format_result(r, path))
                print()
        else:
            print(f"path not found: {path}", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("error: ast-grep (sg) not found. install from https://ast-grep.github.io", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
