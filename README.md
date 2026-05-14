# codetre

AST-based code structure tree tool.

Extracts classes, functions, methods and their call relationships into
a clean hierarchical view. Uses **ast-grep** for AST-level accuracy
across multiple languages.

## Requirements

- Python ≥ 3.10
- [ast-grep](https://ast-grep.github.io) (`sg`) installed and on PATH

## Installation

```bash
pip install codetre
```

## Usage

```bash
# Scan current directory
codetre

# Scan specific directory
codetre src/

# Scan single file
codetre src/main.py

# Scan multiple files / directories
codetre src/main.py tests/

# JSON output
codetre --json src/

# Exclude patterns
codetre --exclude "test_*" --exclude "*_gen.py" src/
```

## Supported Languages

Python, JavaScript, TypeScript, Go, C, C++, Java, Rust, Ruby,
Kotlin, Scala, C#, PHP, Swift, Lua, Bash, and more.

## Output Example

```
# format: name:start,count  -> [file-local ref, ...]

file: src/services/auth.py,84
  import hashlib
  import jwt

  class AuthService:9,76
    func __init__:14,7 -> [_load_secrets]
    func login:22,20  -> [_generate_token, _verify_password]
    func validate_token:43,20
    func _load_secrets:64,12
    func _generate_token:77,4
    func _verify_password:82,3
  func logout:32,8
  var SECRET_KEY:6

file: src/main.py,39
  import os
  from .services import AuthService

  class App:8,32
    func register_user:15,8
    func place_order:24,15 -> [validate_token, create_order]
  func create_app:4,3
  var VERSION:1
```

Each symbol shows `kind name:start_line,line_count`. Container symbols
(class/struct/interface) have their children indented underneath.
Call relationships appear as `-> [callee, ...]`.

## License

MIT
