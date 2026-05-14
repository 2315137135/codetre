"""Smoke tests for codetre — run with `python -m tests.test_smoke`."""

import os
import sys
import json
import subprocess
import tempfile

CODETRE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = """
def greet(name):
    return f"hello {name}"

class Greeter:
    def __init__(self, prefix):
        self.prefix = prefix

    def greet(self, name):
        return self.prefix + greet(name)
"""

FAILED = 0


def check(label: str, ok: bool, detail: str = ""):
    global FAILED
    if ok:
        print(f"  ok  {label}")
    else:
        print(f"FAIL {label}")
        if detail:
            for line in detail.strip().splitlines():
                print(f"      {line}")
        FAILED += 1


def run_codetre(*args: str):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.path.join(CODETRE_DIR, "src")}
    r = subprocess.run(
        [sys.executable, "-m", "codetre", *args],
        capture_output=True, text=True, cwd=CODETRE_DIR, env=env, timeout=30,
    )
    return r


if __name__ == "__main__":
    # ---
    print("=== scan single Python file ===")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "greeter.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

        r = run_codetre(src)
        check("exit code 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("has file line", "file: greeter.py" in r.stdout, r.stdout)
        check("has class", "class Greeter:" in r.stdout, r.stdout)
        check("has greet func", "func greet:" in r.stdout, r.stdout)
        check("has __init__ func", "func __init__:" in r.stdout, r.stdout)
        check("has call chain", "-> [greet]" in r.stdout, r.stdout)

    # ---
    print("=== JSON output ===")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "greeter.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

        r = run_codetre("--json", src)
        check("exit code 0", r.returncode == 0, f"got {r.returncode}")
        try:
            data = json.loads(r.stdout)
            check("JSON parseable", True)
            check("JSON has file field", "file" in data, json.dumps(data, indent=2))
            check("JSON has symbols", len(data["symbols"]) > 0, str(len(data["symbols"])))
        except json.JSONDecodeError as e:
            check("JSON parseable", False, str(e))

    # ---
    print("=== --version ===")
    r = run_codetre("--version")
    check("exit code 0", r.returncode == 0)
    check("version string", r.stdout.strip().startswith("codetre "))

    # ---
    print("=== empty directory ===")
    with tempfile.TemporaryDirectory() as tmp:
        r = run_codetre("--quiet", tmp)
        check("exit code 2 (no symbols)", r.returncode == 2, f"got {r.returncode}")

    # ---
    print("=== --exclude ===")
    with tempfile.TemporaryDirectory() as tmp:
        src1 = os.path.join(tmp, "keep.py")
        src2 = os.path.join(tmp, "ignore_me.py")
        with open(src1, "w") as f:
            f.write("def keep(): pass")
        with open(src2, "w") as f:
            f.write("def ignore(): pass")
        r = run_codetre("--exclude", "ignore_*", tmp)
        check("exit code 0", r.returncode == 0)
        check("keep.py included", "keep.py" in r.stdout, r.stdout)
        check("ignore_me.py excluded", "ignore_me.py" not in r.stdout, r.stdout)

    # ---
    print("=== TS class methods and properties ===")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "app.ts")
        with open(src, "w", encoding="utf-8") as f:
            f.write("""
class UserService {
    private name: string;
    private age: number;

    constructor(name: string, age: number) {
        this.name = name;
    }

    getName(): string {
        return this.name;
    }

    async save(): Promise<boolean> {
        return true;
    }
}

const MAX_RETRIES = 3;
let counter = 0;

function helper() {
    return 42;
}
""")
        r = run_codetre(src)
        check("TS exit code 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("TS class detected", "class UserService:" in r.stdout, r.stdout)
        check("TS constructor detected", "func constructor:" in r.stdout, r.stdout)
        check("TS method detected", "func getName:" in r.stdout, r.stdout)
        check("TS async method detected", "func save:" in r.stdout, r.stdout)
        check("TS field detected", "field name:" in r.stdout, r.stdout)
        check("TS const detected", "var MAX_RETRIES:" in r.stdout, r.stdout)
        check("TS let detected", "var counter:" in r.stdout, r.stdout)
        check("TS function detected", "func helper:" in r.stdout, r.stdout)

    # ---
    print("=== .gitignore from target directory + CWD ===")
    with tempfile.TemporaryDirectory() as tmp:
        subdir = os.path.join(tmp, "src")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "keep.py"), "w") as f:
            f.write("def keep(): pass")
        with open(os.path.join(subdir, "ignore.py"), "w") as f:
            f.write("def ignore(): pass")
        with open(os.path.join(subdir, "also_ignore.py"), "w") as f:
            f.write("def ignore2(): pass")
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("ignore.py")
        with open(os.path.join(subdir, ".gitignore"), "w") as f:
            f.write("also_ignore.py")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8",
               "PYTHONPATH": os.path.join(CODETRE_DIR, "src")}
        r = subprocess.run(
            [sys.executable, "-m", "codetre", subdir],
            capture_output=True, text=True, cwd=tmp, env=env, timeout=30,
        )
        check("gitignore exit 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("keep.py included", "keep.py" in r.stdout, r.stdout)
        check("ignore.py excluded by CWD gitignore", "ignore.py" not in r.stdout, r.stdout)
        check("also_ignore.py excluded by target gitignore", "also_ignore.py" not in r.stdout, r.stdout)

    # ---
    print("=== scan multiple files ===")
    with tempfile.TemporaryDirectory() as tmp:
        src1 = os.path.join(tmp, "a.py")
        src2 = os.path.join(tmp, "b.py")
        with open(src1, "w", encoding="utf-8") as f:
            f.write("def foo(): pass")
        with open(src2, "w", encoding="utf-8") as f:
            f.write("def bar(): pass")
        r = run_codetre(src1, src2)
        check("multi-file exit 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("multi-file has a.py", "a.py" in r.stdout, r.stdout)
        check("multi-file has b.py", "b.py" in r.stdout, r.stdout)
        check("multi-file has foo", "func foo:" in r.stdout, r.stdout)
        check("multi-file has bar", "func bar:" in r.stdout, r.stdout)

    # ---
    print("=== scan mix of file and directory ===")
    with tempfile.TemporaryDirectory() as tmp:
        src1 = os.path.join(tmp, "a.py")
        subdir = os.path.join(tmp, "sub")
        os.makedirs(subdir)
        src2 = os.path.join(subdir, "b.py")
        with open(src1, "w", encoding="utf-8") as f:
            f.write("def foo(): pass")
        with open(src2, "w", encoding="utf-8") as f:
            f.write("def bar(): pass")
        r = run_codetre(src1, subdir)
        check("mix exit 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("mix has a.py", "a.py" in r.stdout, r.stdout)
        check("mix has b.py", "b.py" in r.stdout, r.stdout)

    # ---
    print("=== scan overlapping paths dedup ===")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "dup.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write("def dup(): pass")
        r = run_codetre(src, tmp)
        check("dedup exit 0", r.returncode == 0, f"got {r.returncode}\n{r.stderr}")
        check("dedup only one dup.py", r.stdout.count("dup.py") == 1, f"count: {r.stdout.count('dup.py')}\n{r.stdout}")

    # ---
    print(f"\n=== {FAILED} failures ===")
    sys.exit(FAILED)
