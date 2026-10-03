from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from jarvis.config import DATA_DIR


_ALLOWED_IMPORTS = {"math", "statistics", "decimal", "fractions", "json", "re", "datetime", "collections", "itertools", "functools"}
_BLOCKED_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "input",
    "globals", "locals", "vars", "breakpoint", "help",
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


def _validate(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    _SandboxValidator().visit(tree)


def python_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code", ""))
    if not code.strip():
        raise ValueError("code est requis.")
    if len(code) > 30000:
        raise ValueError("Code trop volumineux pour le sandbox.")

    _validate(code)

    sandbox_root = DATA_DIR / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)

    wrapper = """import builtins
import math, statistics, decimal, fractions, json, re, datetime, collections, itertools, functools

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "len", "list", "map", "max", "min", "print", "range", "repr",
        "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip"
    )
}
SAFE_BUILTINS["Exception"] = Exception
SAFE_GLOBALS = {
    "__builtins__": SAFE_BUILTINS,
    "math": math,
    "statistics": statistics,
    "decimal": decimal,
    "fractions": fractions,
    "json": json,
    "re": re,
    "datetime": datetime,
    "collections": collections,
    "itertools": itertools,
    "functools": functools,
}
USER_CODE = %s
exec(compile(USER_CODE, "<jarvis-sandbox>", "exec"), SAFE_GLOBALS, {})
""" % json.dumps(code)

    timeout = max(1, min(int(args.get("timeout_seconds", 5) or 5), 10))
    with tempfile.TemporaryDirectory(prefix="run-", dir=sandbox_root) as tmp:
        script = Path(tmp) / "runner.py"
        script.write_text(wrapper, encoding="utf-8")

        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Sandbox interrompu après {timeout} secondes.") from exc

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "restricted": True,
    }
