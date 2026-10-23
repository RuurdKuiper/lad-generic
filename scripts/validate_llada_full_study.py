#!/usr/bin/env python3
"""Validate frozen test answers and feasibility using independent correct code."""

import json
import math
from pathlib import Path
import subprocess
import sys

from llada_full_study_tasks import tasks, ROOT

OUT = ROOT / "artifacts/bigram/llada_ngram_settings_full"
REFERENCE = {
    "sum_even": """def sum_even(nums):
    return sum(x for x in nums if x % 2 == 0)
""",
    "balanced": """def balanced(s):
    stack = []
    pairs = dict(zip(')]}', '([{'))
    for c in s:
        if c in '([{': stack.append(c)
        elif c in pairs and (not stack or stack.pop() != pairs[c]): return False
    return not stack
""",
    "is_palindrome": """def is_palindrome(text):
    s = ''.join(c.lower() for c in text if c.isalnum())
    return s == s[::-1]
""",
    "fibonacci": """def fibonacci(n):
    result = []
    a, b = 0, 1
    for _ in range(max(0, n)):
        result.append(a)
        a, b = b, a + b
    return result
""",
    "deduplicate": """def deduplicate(items):
    return list(dict.fromkeys(items))
""",
    "binary_search": """def binary_search(nums, target):
    low, high = 0, len(nums)-1
    while low <= high:
        mid = (low+high)//2
        if nums[mid] == target: return mid
        if nums[mid] < target: low = mid+1
        else: high = mid-1
    return -1
""",
    "word_counts": """def word_counts(text):
    words = text.lower().split()
    return {w: words.count(w) for w in words}
""",
    "merge_sorted": """def merge_sorted(a, b):
    if not a: return b.copy()
    if not b: return a.copy()
    if a[0] <= b[0]: return [a[0]] + merge_sorted(a[1:], b)
    return [b[0]] + merge_sorted(a, b[1:])
""",
    "flatten": """def flatten(rows):
    return [x for row in rows for x in row]
""",
    "fizzbuzz": """def fizzbuzz(n):
    return ['FizzBuzz' if i%15==0 else 'Fizz' if i%3==0 else 'Buzz' if i%5==0 else str(i) for i in range(1,n+1)]
""",
    "factorial": """import math
def factorial(n):
    return math.factorial(n)
""",
    "count_vowels": """def count_vowels(text):
    return sum(c.lower() in 'aeiou' for c in text)
""",
    "gcd": """def gcd(a, b):
    while b: a, b = b, a%b
    return a
""",
    "is_prime": """def is_prime(n):
    return n>1 and all(n%d for d in range(2,int(n**0.5)+1))
""",
    "reverse_words": """def reverse_words(text):
    return ' '.join(reversed(text.split()))
""",
    "clamp": """def clamp(x, low, high):
    return min(max(x, low), high)
""",
    "transpose": """def transpose(matrix):
    return [list(row) for row in zip(*matrix)]
""",
    "chunk_list": """def chunk_list(items, size):
    return [items[i:i+size] for i in range(0,len(items),size)]
""",
    "max_run": """from itertools import groupby
def max_run(nums):
    return max((len(list(g)) for _,g in groupby(nums)),default=0)
""",
    "unique_sorted": """def unique_sorted(nums):
    return sorted(set(nums))
""",
}


def main():
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        ROOT
        / "base_models/models--GSAI-ML--LLaDA-8B-Instruct/snapshots/08b83a6feb34df1a6011b80c3c00c7563e963b07",
        local_files_only=True,
    )
    records = []
    for task in tasks():
        if task["category"] != "code":
            continue
        code = REFERENCE[task["id"]]
        payload = dict(
            code=code,
            function=task["function"],
            cases=task["cases"],
            forbidden_calls=task["forbidden_calls"],
        )
        run = subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROOT / "scripts/check_llada_full_study_code.py"),
                "--worker",
            ],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=5,
            env={"PATH": "/usr/bin:/bin"},
        )
        assert run.returncode == 0, (task["id"], run.stderr)
        checked = json.loads(run.stdout)
        assert (
            all(c["passed"] for c in checked["checks"])
            and not checked["constraint_violations"]
        ), (task["id"], checked)
        tokens = len(tokenizer.encode(code, add_special_tokens=False))
        records.append(
            dict(
                task=task["id"],
                tests=len(task["cases"]),
                all_pass=True,
                reference_tokens=tokens,
                fits_128=tokens <= 128,
            )
        )
    assert all(r["fits_128"] for r in records), records
    math_answers = {
        "algebra": [(9 + 6 - 4) / (3 - 2)],
        "train": [240 / (120 / 60 + 120 / 40)],
        "fraction_equation": [(24 + 6) / (9 - 4)],
        "discount_tax": [80 * 0.75 * 1.1],
        "rectangle": [(34 / 2 - 3) / 2, (34 / 2 + 3) / 2],
        "marbles": [5 / (5 + 3 + 2)],
        "dice": [6 / 36],
        "compound": [1000 * 1.05**2],
        "pipes": [1 / (1 / 6 + 1 / 3)],
        "mixture": [(2 * 0.2 + 3 * 0.4) / 5 * 100],
        "speed_units": [72 * 1000 / 3600 * 10],
        "arithmetic_series": [5 + 19 * 4, 20 / 2 * (5 + 5 + 19 * 4)],
        "triangle": [math.hypot(6, 8), 6 * 8 / 2],
        "mean": [5 * 14 - 4 * 12],
        "ratio": [32 / (3 + 5) * 3, 32 / (3 + 5) * 5],
        "choose_pair": [math.comb(7, 2)],
        "percent_change": [(100 - 80) / 80 * 100],
        "exponent": [math.log2(32) - 1],
        "quadratic": [(5 - math.sqrt(25 - 24)) / 2, (5 + math.sqrt(25 - 24)) / 2],
        "ages": [(42 - 2 * 6) / 3 * 2, (42 - 2 * 6) / 3],
    }
    for task in tasks():
        if task["category"] == "math":
            assert all(
                math.isclose(a, b, rel_tol=1e-12)
                for a, b in zip(task["answers"], math_answers[task["id"]])
            ), task
    report = dict(
        code_reference_checks=records,
        total_code_tests=sum(r["tests"] for r in records),
        all_code_references_pass=True,
        all_fit_128=True,
        math_references_validated=20,
    )
    (OUT / "reference_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "reference_code.json").write_text(json.dumps(REFERENCE, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
