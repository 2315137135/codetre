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
```

## Supported Languages

Python, JavaScript, TypeScript, Go, C, C++, Java, Rust, Ruby,
Kotlin, Scala, C#, PHP, Swift, Lua, Bash, and more.

## Output Example

```
file: src/services/auth.py
  class AuthService:9~40
    func login:14~20  -> call[_generate_token, _verify_password]
    func validate_token:22~30
    func logout:32~34

file: src/main.py
  class App:8~39
    func register_user:15~19
    func place_order:21~30  -> call[validate_token, create_order, approve_order]
```

## License

MIT
