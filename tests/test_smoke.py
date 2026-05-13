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
    check("has call chain", "-> call[greet]" in r.stdout, r.stdout)

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
print(f"\n=== {FAILED} failures ===")
sys.exit(FAILED)
