#!/usr/bin/env python3
"""Syntax and fixed edge-case checks in restricted, resource-limited workers."""

import ast
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings_full"
IMPORTS = {
    "math": {"sqrt", "isqrt", "factorial", "gcd", "floor", "ceil", "inf"},
    "collections": {"Counter", "defaultdict", "deque"},
    "typing": {
        "List",
        "Dict",
        "Tuple",
        "Any",
        "Iterable",
        "Sequence",
        "Optional",
        "Set",
    },
    "itertools": {"chain", "groupby", "islice"},
    "functools": {"reduce", "lru_cache", "cache"},
    "re": {"sub", "findall", "split", "fullmatch", "match", "IGNORECASE", "I"},
    "string": {"ascii_letters", "ascii_lowercase", "ascii_uppercase", "digits"},
}
METHODS = {
    "append",
    "pop",
    "get",
    "items",
    "values",
    "keys",
    "extend",
    "count",
    "index",
    "lower",
    "upper",
    "strip",
    "lstrip",
    "rstrip",
    "split",
    "rsplit",
    "splitlines",
    "join",
    "replace",
    "isalnum",
    "isalpha",
    "isdigit",
    "isspace",
    "startswith",
    "endswith",
    "add",
    "discard",
    "remove",
    "update",
    "setdefault",
    "sort",
    "reverse",
    "copy",
    "clear",
    "union",
    "intersection",
    "group",
    "groups",
    "fromkeys",
    "translate",
    "maketrans",
} | set.union(*IMPORTS.values())
BUILTINS = {
    "sum",
    "len",
    "range",
    "enumerate",
    "zip",
    "all",
    "any",
    "isinstance",
    "int",
    "float",
    "str",
    "list",
    "dict",
    "set",
    "tuple",
    "bool",
    "min",
    "max",
    "abs",
    "reversed",
    "sorted",
    "round",
    "divmod",
    "pow",
    "map",
    "filter",
    "next",
    "iter",
    "slice",
    "repr",
    "print",
    "ValueError",
    "TypeError",
    "Exception",
    "ZeroDivisionError",
    "AssertionError",
    "StopIteration",
}


def extract(text):
    match = re.search(r"```(?:python|py)?\s*\n(.*?)(?:```|\Z)", text, re.S)
    return match[1].strip() if match else text.strip()


def validate(code, name):
    tree = ast.parse(code)
    if not any(isinstance(n, ast.FunctionDef) and n.name == name for n in tree.body):
        raise LookupError("Required function missing")
    for n in ast.walk(tree):
        if isinstance(
            n,
            (
                ast.ClassDef,
                ast.Global,
                ast.Nonlocal,
                ast.AsyncFunctionDef,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            raise PermissionError("Outside restricted function subset")
        if isinstance(n, ast.Name) and n.id.startswith("__"):
            raise PermissionError("Dunder identifier")
        if isinstance(n, ast.Attribute) and n.attr not in METHODS:
            raise PermissionError("Unreviewed attribute: " + n.attr)
        if isinstance(n, ast.Import) and any(a.name not in IMPORTS for a in n.names):
            raise PermissionError("Unreviewed import")
        if isinstance(n, ast.ImportFrom) and (
            n.level
            or n.module not in IMPORTS
            or any(a.name not in IMPORTS[n.module] for a in n.names)
        ):
            raise PermissionError("Unreviewed import-from")
    return tree


def equal(actual, expected):
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, float):
        return type(actual) in (int, float) and math.isclose(
            actual, expected, rel_tol=1e-9, abs_tol=1e-9
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(equal(a, b) for a, b in zip(actual, expected))
        )
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(equal(actual[k], v) for k, v in expected.items())
        )
    return type(actual) is type(expected) and actual == expected


def worker():
    import builtins
    import copy
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    except (ValueError, OSError):
        pass
    p = json.load(sys.stdin)
    tree = validate(p["code"], p["function"])
    forbidden = set(p.get("forbidden_calls", []))
    violations = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and n.func.id in forbidden)
            or (isinstance(n.func, ast.Attribute) and n.func.attr in forbidden)
        ):
            violations.append(ast.unparse(n.func))

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        fromlist = fromlist or ()
        if (
            level
            or name not in IMPORTS
            or any(x not in IMPORTS[name] for x in fromlist)
        ):
            raise ImportError("Restricted import")
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace = {
        "__builtins__": {key: getattr(builtins, key) for key in BUILTINS},
        "__name__": "generated",
    }
    namespace["__builtins__"]["__import__"] = safe_import
    checks = []
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(tree, "generated", "exec"), namespace)
        for case in p["cases"]:
            try:
                value = namespace[p["function"]](*copy.deepcopy(case["args"]))
                checks.append(
                    dict(
                        passed=equal(value, case["expected"]),
                        actual=repr(value)[:180],
                        expected=repr(case["expected"])[:180],
                    )
                )
            except Exception as exc:
                checks.append(
                    dict(passed=False, error=type(exc).__name__ + ": " + str(exc)[:180])
                )
    print(json.dumps(dict(checks=checks, constraint_violations=violations)))


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    tasks = {t["id"]: t for t in manifest["tasks"]}
    rows = []
    for phase in ["main", "sample", "confidence_zero"]:
        path = OUT / phase / "results.jsonl"
        if path.exists():
            rows.extend(json.loads(s) for s in path.read_text().splitlines())
    cachepath = OUT / "code_cache.json"
    cache = json.loads(cachepath.read_text()) if cachepath.exists() else {}
    records = {}
    for row in rows:
        if row["category"] != "code":
            continue
        task = tasks[row["task"]]
        code = extract(row["text"])
        digest = hashlib.sha256(code.encode()).hexdigest()
        cachekey = row["task"] + ":" + digest
        if cachekey in cache and cache[cachekey]["status"] in {
            "executed",
            "syntax_error",
            "missing_function",
            "timeout",
        }:
            result = dict(cache[cachekey])
        else:
            result = dict(
                code_sha256=digest, total=len(task["cases"]), passed=0, all_pass=False
            )
            try:
                validate(code, task["function"])
            except SyntaxError as exc:
                result.update(status="syntax_error", error=str(exc), score=0)
            except LookupError as exc:
                result.update(status="missing_function", error=str(exc), score=0)
            except PermissionError as exc:
                result.update(
                    status="policy_blocked", error=str(exc), all_pass=None, score=None
                )
            else:
                try:
                    payload = dict(
                        code=code,
                        function=task["function"],
                        cases=task["cases"],
                        forbidden_calls=task["forbidden_calls"],
                    )
                    with tempfile.TemporaryDirectory(prefix="llada-full-code-") as tmp:
                        run = subprocess.run(
                            [
                                sys.executable,
                                "-I",
                                str(Path(__file__).resolve()),
                                "--worker",
                            ],
                            input=json.dumps(payload),
                            text=True,
                            capture_output=True,
                            timeout=5,
                            cwd=tmp,
                            env={"PATH": "/usr/bin:/bin"},
                        )
                    if run.returncode:
                        raise RuntimeError(run.stderr[-600:])
                    data = json.loads(run.stdout)
                    passed = sum(c["passed"] for c in data["checks"])
                    success = (
                        passed == len(task["cases"])
                        and not data["constraint_violations"]
                    )
                    result.update(
                        status="executed",
                        passed=passed,
                        all_pass=success,
                        score=3 if success else 2 if passed else 1,
                        **data,
                    )
                except subprocess.TimeoutExpired:
                    result.update(status="timeout", score=0)
                except Exception as exc:
                    result.update(status="runtime_error", score=0, error=str(exc))
            cache[cachekey] = result
        records[row["key"]] = dict(
            result, sha256=row["sha256"], phase=row["phase"], task=row["task"]
        )
    (OUT / "code_checks.json").write_text(json.dumps(records, indent=2) + "\n")
    cachepath.write_text(json.dumps(cache, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                checked=len(records),
                all_pass=sum(r["all_pass"] is True for r in records.values()),
                pending_policy_review=sum(
                    r["status"] == "policy_blocked" for r in records.values()
                ),
                unique_code=len(cache),
            )
        )
    )


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker()
    else:
        main()
