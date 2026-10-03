from __future__ import annotations

import ast
import builtins
import json
import sys

_ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "decimal",
    "fractions",
    "json",
    "re",
    "datetime",
    "collections",
    "itertools",
    "functools",
}
_BLOCKED_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "globals",
    "locals",
    "vars",
    "breakpoint",
    "help",
}


class _SandboxValidator(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            if root not in _ALLOWED_IMPORTS:
                raise ValueError(f"Import interdit dans le sandbox : {root}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".", 1)[0]
        if root not in _ALLOWED_IMPORTS:
            raise ValueError(f"Import interdit dans le sandbox : {root}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"Nom interdit dans le sandbox : {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError("Accès aux attributs dunder interdit dans le sandbox.")
        self.generic_visit(node)


def validate_sandbox_code(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    _SandboxValidator().visit(tree)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import interdit dans le sandbox : {root}")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _execute(code: str) -> None:
    safe_builtins = {
        name: getattr(builtins, name)
        for name in (
            "abs",
            "all",
            "any",
            "bool",
            "dict",
            "enumerate",
            "filter",
            "float",
            "int",
            "len",
            "list",
            "map",
            "max",
            "min",
            "print",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "sorted",
            "str",
            "sum",
            "tuple",
            "zip",
        )
    }
    safe_builtins["Exception"] = Exception
    safe_builtins["__import__"] = _safe_import
    safe_globals = {"__builtins__": safe_builtins}
    exec(compile(code, "<jarvis-sandbox>", "exec"), safe_globals, {})


def run_sandbox_runner() -> int:
    """Read, revalidate, and execute one restricted request from stdin."""
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("Requête sandbox invalide.")
        code = payload.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code est requis.")
        if len(code) > 30000:
            raise ValueError("Code trop volumineux pour le sandbox.")
        validate_sandbox_code(code)
        _execute(code)
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_sandbox_runner())