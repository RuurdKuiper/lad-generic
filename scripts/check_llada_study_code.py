#!/usr/bin/env python3
"""Run pure generated functions against fixed tests in restricted subprocesses."""

import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings"
TESTS = {
    "sum_even": [
        (v, sum(x for x in v if x % 2 == 0))
        for v in [
            [],
            [1, 2, 3, 4],
            [-4, -3, -2, -1],
            [0],
            [2, 2],
            [-2, 2],
            [3, 5, 7],
            list(range(-10, 11)),
            [10**9, 1, 2],
            [1],
            [-10, 10, 12],
        ]
    ],
    "balanced": [
        (s, want)
        for s, want in [
            ("", True),
            ("()", True),
            ("([]{})", True),
            ("([)]", False),
            ("(", False),
            (")", False),
            ("a(b[c]{d})e", True),
            ("(()", False),
            ("[()]", True),
            ("()[]{}", True),
            ("{[()]}", True),
            ("[(])", False),
            ("())(", False),
            ("text only", True),
            ("([{}])", True),
            ("{[(])}", False),
        ]
    ],
}
ALLOWED_CALLS = {
    "sum",
    "len",
    "range",
    "enumerate",
    "zip",
    "all",
    "any",
    "isinstance",
    "int",
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
    "ValueError",
}
ALLOWED_METHODS = {
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
    "strip",
}


def extract(text):
    match = re.search(r"```(?:python|py)?\s*\n(.*?)(?:```|\Z)", text, re.S)
    return match[1].strip() if match else text.strip()


def validate(code, name):
    tree = ast.parse(code)
    if not any(isinstance(n, ast.FunctionDef) and n.name == name for n in tree.body):
        raise ValueError("Required function missing")
    if any(
        not isinstance(n, ast.FunctionDef)
        and not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
        for n in tree.body
    ):
        raise ValueError("Top-level code beyond function definitions")
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for n in ast.walk(tree):
        if isinstance(
            n,
            (
                ast.Import,
                ast.ImportFrom,
                ast.ClassDef,
                ast.Global,
                ast.Nonlocal,
                ast.AsyncFunctionDef,
                ast.With,
                ast.Try,
            ),
        ):
            raise ValueError("Code outside pure function subset")
        if isinstance(n, ast.Name) and n.id.startswith("__"):
            raise ValueError("Dunder identifier")
        if isinstance(n, ast.Attribute) and n.attr not in ALLOWED_METHODS:
            raise ValueError("Attribute outside pure function subset")
        if isinstance(n, ast.FunctionDef) and (
            n.decorator_list or n.args.defaults or n.args.kw_defaults
        ):
            raise ValueError("Decorators/default arguments need separate review")
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id not in ALLOWED_CALLS | names:
                raise ValueError("Call outside pure function subset")
            if not isinstance(n.func, (ast.Name, ast.Attribute)):
                raise ValueError("Indirect call")
    return tree


def worker():
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    payload = json.load(sys.stdin)
    code = payload["code"]
    name = payload["name"]
    validate(code, name)
    import builtins

    allowed = {key: getattr(builtins, key) for key in ALLOWED_CALLS}
    namespace = {"__builtins__": allowed}
    exec(compile(code, "generated", "exec"), namespace)
    results = []
    for inp, want in TESTS[name]:
        try:
            value = namespace[name](inp.copy() if isinstance(inp, list) else inp)
            results.append(
                dict(
                    passed=type(value) is type(want) and value == want,
                    actual=repr(value)[:150],
                    expected=repr(want),
                )
            )
        except Exception as exc:
            results.append(
                dict(passed=False, error=type(exc).__name__ + ": " + str(exc)[:150])
            )
    print(json.dumps(results))


def main():
    rows = [json.loads(s) for s in (OUT / "results.jsonl").read_text().splitlines()]
    records = {}
    for row in rows:
        if row["category"] != "code":
            continue
        code = extract(row["text"])
        record = dict(sha256=row["sha256"], code=code, total=len(TESTS[row["task"]]))
        try:
            validate(code, row["task"])
        except (SyntaxError, ValueError) as exc:
            record.update(
                syntax_valid=not isinstance(exc, SyntaxError),
                executable=False,
                passed=0,
                all_pass=False,
                error=str(exc),
                score=0,
            )
        else:
            try:
                with tempfile.TemporaryDirectory(prefix="llada-code-check-") as folder:
                    run = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            str(Path(__file__).resolve()),
                            "--worker",
                        ],
                        input=json.dumps(dict(code=code, name=row["task"])),
                        text=True,
                        capture_output=True,
                        timeout=4,
                        cwd=folder,
                        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"},
                    )
                if run.returncode:
                    raise RuntimeError(run.stderr[-500:])
                checks = json.loads(run.stdout)
                passed = sum(t["passed"] for t in checks)
                record.update(
                    syntax_valid=True,
                    executable=True,
                    passed=passed,
                    all_pass=passed == len(checks),
                    checks=checks,
                    score=3 if passed == len(checks) else 2 if passed else 1,
                )
            except Exception as exc:
                record.update(
                    syntax_valid=True,
                    executable=False,
                    passed=0,
                    all_pass=False,
                    error=str(exc),
                    score=0,
                )
        records[row["key"]] = record
    (OUT / "code_checks.json").write_text(json.dumps(records, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                checked=len(records),
                all_pass=sum(r["all_pass"] for r in records.values()),
            )
        )
    )


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker()
    else:
        main()
