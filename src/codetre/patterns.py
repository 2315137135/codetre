"""Language definition patterns for codetre."""

_GET_NAME = lambda m: m['metaVariables']['single']['NAME']['text'].split('::')[-1].split('.')[-1]
_GET_OBJ_METHOD = lambda m: m['metaVariables']['single']['NAME']['text']

_COMMON_CALL = [('$NAME($$$ARGS)', _GET_NAME), ('$OBJ.$NAME($$$ARGS)', _GET_OBJ_METHOD)]
_COMMON_CALL_NO_OBJ = [('$NAME($$$ARGS)', _GET_NAME)]

CALL_PATTERNS = {
    'python':      _COMMON_CALL,
    'javascript':  _COMMON_CALL,
    'typescript':  _COMMON_CALL,
    'tsx':         _COMMON_CALL,
    'cpp':         [*_COMMON_CALL,
                    ('$NAME($$$ARGS);', _GET_NAME),
                    ('$VAR = $NAME($$$ARGS)', _GET_NAME),
                    ('$TYPE $VAR = $NAME($$$ARGS)', _GET_NAME)],
    'c':           [('$NAME($$$ARGS)', _GET_NAME),
                    ('$NAME($$$ARGS);', _GET_NAME),
                    ('$VAR = $NAME($$$ARGS)', _GET_NAME),
                    ('$TYPE $VAR = $NAME($$$ARGS)', _GET_NAME)],
    'go':          _COMMON_CALL,
    'rust':        _COMMON_CALL,
    'ruby':        _COMMON_CALL,
    'java':        _COMMON_CALL,
    'kotlin':      _COMMON_CALL,
    'scala':       _COMMON_CALL,
    'csharp':      _COMMON_CALL,
    'php':         _COMMON_CALL,
    'swift':       _COMMON_CALL,
    'lua':         _COMMON_CALL,
    'bash':        _COMMON_CALL_NO_OBJ,
    'elixir':      _COMMON_CALL_NO_OBJ,
    'haskell':     _COMMON_CALL_NO_OBJ,
    'solidity':    _COMMON_CALL,
}

DEF_PATTERNS = {
    'python':      [('class $NAME', 'class'),                    ('def $NAME', 'func')],
    'javascript':  [('class $NAME', 'class'),                    ('function $NAME($$$ARGS)', 'func')],
    'typescript':  [('class $NAME', 'class'),                    ('interface $NAME { $$$BODY }', 'interface')],
    'tsx':         [('class $NAME', 'class'),                    ('interface $NAME { $$$BODY }', 'interface')],
    'cpp':         [('class $NAME', 'class'),                    ('$TYPE $NAME($$$PARAMS) { $$$BODY }', 'func')],
    'c':           [('$TYPE $NAME($$$PARAMS) { $$$BODY }', 'func')],
    'go':          [('type $NAME struct { $$$BODY }', 'struct'), ('type $NAME interface { $$$BODY }', 'interface'),
                    ('func $NAME($$$PARAMS)', 'func')],
    'rust':        [('struct $NAME { $$$BODY }', 'struct'),      ('trait $NAME { $$$BODY }', 'interface'),
                    ('impl $$$_ for $NAME { $$$BODY }', 'impl'), ('fn $NAME', 'func')],
    'ruby':        [('class $NAME', 'class'),                    ('def $NAME', 'func')],
    'java':        [('class $NAME { $$$BODY }', 'class'),        ('public class $NAME { $$$BODY }', 'class'),
                    ('interface $NAME { $$$BODY }', 'interface'),
                    ('$TYPE $NAME($$$PARAMS) { $$$BODY }', 'func'),
                    ('public $TYPE $NAME($$$PARAMS) { $$$BODY }', 'func'),
                    ('$NAME($$$PARAMS) { $$$BODY }', 'func')],
    'kotlin':      [('class $NAME', 'class'),                    ('interface $NAME { $$$BODY }', 'interface'),
                    ('fun $NAME($$$PARAMS)', 'func')],
    'scala':       [('class $NAME', 'class'),                    ('trait $NAME { $$$BODY }', 'interface'),
                    ('def $NAME($$$PARAMS)', 'func')],
    'csharp':      [('class $NAME', 'class'),                    ('interface $NAME { $$$BODY }', 'interface'),
                    ('$TYPE $NAME($$$PARAMS) { $$$BODY }', 'func')],
    'php':         [('class $NAME', 'class'),                    ('interface $NAME { $$$BODY }', 'interface'),
                    ('function $NAME($$$PARAMS)', 'func')],
    'swift':       [('class $NAME', 'class'),                    ('protocol $NAME { $$$BODY }', 'interface'),
                    ('func $NAME($$$PARAMS)', 'func')],
    'lua':         [('function $NAME($$$PARAMS)', 'func')],
    'bash':        [('function $NAME()', 'func')],
    'elixir':      [('defmodule $NAME', 'class'),                ('def $NAME($$$PARAMS)', 'func'),
                    ('defp $NAME($$$PARAMS)', 'func')],
    'haskell':     [('$NAME :: $$$TYPE', 'func')],
    'solidity':    [('contract $NAME { $$$BODY }', 'class'),     ('function $NAME($$$PARAMS)', 'func')],
}

# Definition kind matchers via sg scan --inline-rules (AST node kind names).
# These supplement DEF_PATTERNS for constructs that can't be expressed as plain patterns.
KIND_DEFS = {
    'javascript':  [('method_definition', 'func'), ('field_definition', 'field'),
                     ('lexical_declaration', 'var'), ('variable_declaration', 'var')],
    'typescript':  [('method_definition', 'func'), ('public_field_definition', 'field'),
                     ('lexical_declaration', 'var'), ('variable_declaration', 'var'),
                     ('function_declaration', 'func')],
    'tsx':         [('method_definition', 'func'), ('public_field_definition', 'field'),
                     ('lexical_declaration', 'var'), ('variable_declaration', 'var'),
                     ('function_declaration', 'func')],
}

IMPORT_PATTERNS = {
    'python':      [('import $NAME', _GET_NAME), ('from $$$_ import $NAME', _GET_NAME)],
    'javascript':  [('import $NAME from $$$_', _GET_NAME), ('import { $NAME } from $$$_', _GET_NAME)],
    'typescript':  [('import $NAME from $$$_', _GET_NAME), ('import { $NAME } from $$$_', _GET_NAME)],
    'tsx':         [('import $NAME from $$$_', _GET_NAME), ('import { $NAME } from $$$_', _GET_NAME)],
    'go':          [('import "$$$_"', _GET_NAME)],
    'rust':        [('use $$$_::$NAME;', _GET_NAME)],
    'java':        [('import $$$_.$NAME;', _GET_NAME)],
    'scala':       [('import $$$_.$NAME', _GET_NAME)],
    'kotlin':      [('import $$$_.$NAME', _GET_NAME)],
    'swift':       [('import $NAME', _GET_NAME)],
    'ruby':        [('require \'$$$_\'', _GET_NAME)],
}

LANG_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.c': 'c', '.h': 'c',
    '.go': 'go',
    '.rs': 'rust', '.rb': 'ruby', '.java': 'java', '.kt': 'kotlin', '.scala': 'scala',
    '.cs': 'csharp', '.php': 'php', '.swift': 'swift',
    '.lua': 'lua', '.sh': 'bash', '.bash': 'bash', '.ex': 'elixir', '.exs': 'elixir',
    '.hs': 'haskell', '.sol': 'solidity',
}
