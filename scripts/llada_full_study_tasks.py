"""Frozen 60-prompt study set, independent tests and stratified selection split."""

from pathlib import Path
import math
import random

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIX = " Return only concise Python code, without explanation or examples."


def case(args, expected):
    return dict(args=args, expected=expected)


CODE = [
    (
        "sum_even",
        "Write Python function sum_even(nums) returning the sum of even integers in nums. Handle an empty list.",
        [
            case([x], sum(v for v in x if v % 2 == 0))
            for x in [
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
    ),
    (
        "balanced",
        "Write Python function balanced(s) checking balanced parentheses (), brackets [], and braces {}. Ignore other characters.",
        [
            case([s], v)
            for s, v in [
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
    ),
    (
        "is_palindrome",
        "Write Python function is_palindrome(text) ignoring case and non-alphanumeric characters. Return a boolean.",
        [
            case([s], v)
            for s, v in [
                ("", True),
                ("a", True),
                ("Aa", True),
                ("ab", False),
                ("A man, a plan, a canal: Panama!", True),
                ("race a car", False),
                ("12321", True),
                ("12a21", True),
                ("No lemon, no melon", True),
                ("0P", False),
                ("!!!", True),
            ]
        ],
    ),
    (
        "fibonacci",
        "Write Python function fibonacci(n) returning a list of the first n Fibonacci numbers, starting with 0, 1. For n <= 0 return [].",
        [
            case([n], v)
            for n, v in [
                (-3, []),
                (0, []),
                (1, [0]),
                (2, [0, 1]),
                (3, [0, 1, 1]),
                (4, [0, 1, 1, 2]),
                (7, [0, 1, 1, 2, 3, 5, 8]),
                (10, [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]),
            ]
        ],
    ),
    (
        "deduplicate",
        "Write Python function deduplicate(items) removing duplicates while preserving first occurrence order. Items are hashable.",
        [
            case([x], list(dict.fromkeys(x)))
            for x in [
                [],
                [1],
                [1, 1, 1],
                [3, 1, 3, 2, 1],
                ["b", "a", "b"],
                [0, -1, 0, 2, -1],
                ["x", "y", "z"],
                [None, None, 1],
                list(range(10)),
                [2, 1, 2, 1, 3, 3],
            ]
        ],
    ),
    (
        "binary_search",
        "Write Python function binary_search(nums, target) for sorted nums, returning its index or -1 if absent. Test lists contain no duplicates.",
        [
            case([x, y], x.index(y) if y in x else -1)
            for x, y in [
                ([], 1),
                ([1], 1),
                ([1], 0),
                ([1, 3], 3),
                ([1, 3], 2),
                ([-5, -1, 0, 4, 9], -5),
                ([-5, -1, 0, 4, 9], 9),
                ([-5, -1, 0, 4, 9], 0),
                ([2, 4, 6, 8], 8),
                ([2, 4, 6, 8], 1),
                ([2, 4, 6, 8], 10),
            ]
        ],
    ),
    (
        "word_counts",
        "Write Python function word_counts(text) returning a dictionary of word frequencies. Split on whitespace and ignore case.",
        [
            case([s], v)
            for s, v in [
                ("", {}),
                ("  ", {}),
                ("Hi", {"hi": 1}),
                ("Hi hi HI", {"hi": 3}),
                ("a b a", {"a": 2, "b": 1}),
                ("red\nblue\tred", {"red": 2, "blue": 1}),
                ("Hello, hello", {"hello,": 1, "hello": 1}),
                ("x  y   x", {"x": 2, "y": 1}),
            ]
        ],
    ),
    (
        "merge_sorted",
        "Write Python function merge_sorted(a, b) merging two sorted integer lists into one sorted list. Do not call sorted() or .sort().",
        [
            case([a, b], sorted(a + b))
            for a, b in [
                ([], []),
                ([1], []),
                ([], [2]),
                ([1], [2]),
                ([2], [1]),
                ([1, 3, 5], [2, 4, 6]),
                ([1, 1], [1, 2]),
                ([-4, -1, 2], [-3, 0, 7]),
                ([1, 2, 3], [9]),
                ([0], [0]),
            ]
        ],
    ),
    (
        "flatten",
        "Write Python function flatten(rows) flattening a list of lists by one level. Preserve order and handle empty lists.",
        [
            case([x], [v for row in x for v in row])
            for x in [
                [],
                [[]],
                [[1]],
                [[1, 2], [], [3]],
                [[1], [2], [3]],
                [[], [], []],
                [["a"], ["b", "c"]],
                [[None], [0, False]],
                [[[1]], [[2]]],
            ]
        ],
    ),
    (
        "fizzbuzz",
        "Write Python function fizzbuzz(n) returning strings for integers 1 through n: Fizz for multiples of 3, Buzz for 5, FizzBuzz for both, otherwise the number as a string.",
        [
            case(
                [n],
                [
                    (
                        "FizzBuzz"
                        if v % 15 == 0
                        else "Fizz" if v % 3 == 0 else "Buzz" if v % 5 == 0 else str(v)
                    )
                    for v in range(1, n + 1)
                ],
            )
            for n in [0, 1, 2, 3, 5, 6, 10, 15, 16, 30]
        ],
    ),
    (
        "factorial",
        "Write Python function factorial(n) returning n factorial for a nonnegative integer n. Remember that 0! = 1.",
        [case([n], math.factorial(n)) for n in [0, 1, 2, 3, 4, 5, 7, 10, 12]],
    ),
    (
        "count_vowels",
        "Write Python function count_vowels(text) counting occurrences of a, e, i, o and u, ignoring case.",
        [
            case([s], sum(c in "aeiou" for c in s.lower()))
            for s in [
                "",
                "a",
                "AEIOU",
                "hello",
                "rhythm",
                "Education",
                "aAa",
                "123!",
                "The quick brown fox",
                "why?",
            ]
        ],
    ),
    (
        "gcd",
        "Write Python function gcd(a, b) returning the greatest common divisor of two nonnegative integers. Return 0 for gcd(0, 0).",
        [
            case([a, b], math.gcd(a, b))
            for a, b in [
                (0, 0),
                (0, 5),
                (7, 0),
                (1, 1),
                (12, 18),
                (18, 12),
                (17, 13),
                (100, 10),
                (48, 180),
                (81, 27),
            ]
        ],
    ),
    (
        "is_prime",
        "Write Python function is_prime(n) returning whether integer n is prime. Integers below 2 are not prime.",
        [
            case(
                [n], n >= 2 and all(n % d for d in range(2, math.isqrt(max(0, n)) + 1))
            )
            for n in [-7, 0, 1, 2, 3, 4, 9, 17, 25, 49, 97, 121, 169]
        ],
    ),
    (
        "reverse_words",
        "Write Python function reverse_words(text) reversing the order of whitespace-separated words, joining the result with single spaces.",
        [
            case([s], " ".join(reversed(s.split())))
            for s in [
                "",
                "a",
                "a b",
                "one two three",
                "  hi  there  ",
                "a\nb\tc",
                "Hello, world!",
                "1 2 3 4",
            ]
        ],
    ),
    (
        "clamp",
        "Write Python function clamp(x, low, high) returning x limited to the inclusive interval [low, high]. Assume low <= high.",
        [
            case([x, a, b], max(a, min(x, b)))
            for x, a, b in [
                (5, 0, 10),
                (-1, 0, 10),
                (12, 0, 10),
                (0, 0, 10),
                (10, 0, 10),
                (5, 3, 3),
                (-5, -9, -2),
                (0, -9, -2),
                (2.5, 1.0, 2.0),
                (-10, -5, 5),
            ]
        ],
    ),
    (
        "transpose",
        "Write Python function transpose(matrix) returning the transpose as a list of lists. Assume a rectangular matrix. Return [] for an empty matrix.",
        [
            case([x], [list(row) for row in zip(*x)])
            for x in [
                [],
                [[]],
                [[], []],
                [[1]],
                [[1, 2, 3]],
                [[1], [2], [3]],
                [[1, 2], [3, 4]],
                [[1, 2, 3], [4, 5, 6]],
                [["a", "b"], ["c", "d"]],
            ]
        ],
    ),
    (
        "chunk_list",
        "Write Python function chunk_list(items, size) splitting a list into consecutive chunks of at most size elements. size is a positive integer; keep a shorter final chunk.",
        [
            case([x, n], [x[i : i + n] for i in range(0, len(x), n)])
            for x, n in [
                ([], 1),
                ([1], 1),
                ([1], 3),
                ([1, 2, 3], 2),
                ([1, 2, 3, 4], 2),
                ([1, 2, 3], 1),
                ([1, 2, 3], 4),
                (list(range(10)), 3),
                (["a", "b", "c", "d"], 3),
            ]
        ],
    ),
    (
        "max_run",
        "Write Python function max_run(nums) returning the length of the longest consecutive run of equal values in a list. Return 0 for an empty list.",
        [
            case([x], v)
            for x, v in [
                ([], 0),
                ([1], 1),
                ([1, 1], 2),
                ([1, 2, 3], 1),
                ([1, 1, 2, 2, 2, 1], 3),
                ([0, 0, 0, 0], 4),
                ([1, 2, 2, 3, 3, 3], 3),
                ([1, 1, 2, 1, 1, 1, 1], 4),
                ([-1, -1, 0], 2),
            ]
        ],
    ),
    (
        "unique_sorted",
        "Write Python function unique_sorted(nums) returning the unique integers of nums in ascending order.",
        [
            case([x], sorted(set(x)))
            for x in [
                [],
                [1],
                [1, 1],
                [3, 1, 3, 2],
                [-1, 2, -1, 0],
                [0, 0],
                list(range(9, -1, -1)),
                [10**9, -(10**9), 0, 10**9],
            ]
        ],
    ),
]

MATH = [
    (
        "algebra",
        "Solve 3(x - 2) + 4 = 2x + 9. Show your steps briefly.",
        [11],
        "x = 11; expand to 3x-2=2x+9, then x-2=9.",
    ),
    (
        "train",
        "A train travels 120 km at 60 km/h and returns the same 120 km at 40 km/h. What is its average speed for the entire trip? Explain briefly.",
        [48],
        "240 km divided by (2+3) hours = 48 km/h.",
    ),
    (
        "fraction_equation",
        "Solve (3x - 2)/4 = (x + 6)/3. Show your steps briefly.",
        [6],
        "9x-6=4x+24, so 5x=30 and x=6.",
    ),
    (
        "discount_tax",
        "An item costs $80 before a 25% discount. A 10% sales tax is then applied to the discounted price. What is the final price? Explain briefly.",
        [66],
        "80*0.75*1.10 = 66 dollars.",
    ),
    (
        "rectangle",
        "A rectangle has perimeter 34 cm. Its length is 3 cm greater than its width. Find its width and length. Show brief working.",
        [7, 10],
        "2(w+w+3)=34; width 7 cm, length 10 cm.",
    ),
    (
        "marbles",
        "A bag contains 5 red, 3 blue and 2 green marbles. One is drawn uniformly at random. What is the probability it is red? Give a fraction and explain briefly.",
        [0.5],
        "5/(5+3+2)=5/10=1/2.",
    ),
    (
        "dice",
        "Two fair six-sided dice are rolled. What is the probability that their sum is 7? Give a fraction and explain briefly.",
        [1 / 6],
        "Six ordered outcomes out of 36: 1/6.",
    ),
    (
        "compound",
        "In a hypothetical arithmetic exercise, $1000 grows by 5% annually, compounded once per year. What is the balance after two years? Show brief working.",
        [1102.5],
        "1000*1.05^2 = 1102.50.",
    ),
    (
        "pipes",
        "One pipe fills an empty tank in 6 hours and another in 3 hours. If both operate together at constant rates, how long does filling take? Explain briefly.",
        [2],
        "Combined rate 1/6+1/3=1/2 tank/hour, so two hours.",
    ),
    (
        "mixture",
        "Mix 2 litres of a 20% salt solution with 3 litres of a 40% salt solution. What is the salt percentage of the mixture? Explain briefly.",
        [32],
        "(2*0.20+3*0.40)/5=0.32, or 32%.",
    ),
    (
        "speed_units",
        "A car moves at a constant 72 km/h for 10 seconds. How many metres does it travel? Explain briefly.",
        [200],
        "72 km/h =20 m/s; multiply by 10s to get 200m.",
    ),
    (
        "arithmetic_series",
        "An arithmetic sequence starts 5, 9, 13, ... . Find its 20th term and the sum of its first 20 terms. Explain briefly.",
        [81, 860],
        "20th term 5+19*4=81; sum 20*(5+81)/2=860.",
    ),
    (
        "triangle",
        "A right triangle has perpendicular sides of 6 cm and 8 cm. Find its hypotenuse and area. Explain briefly.",
        [10, 24],
        "Hypotenuse sqrt(36+64)=10cm; area 6*8/2=24 square cm.",
    ),
    (
        "mean",
        "Four numbers have mean 12. A fifth number is added, raising the mean of all five to 14. What is the fifth number? Explain briefly.",
        [22],
        "5*14 - 4*12=70-48=22.",
    ),
    (
        "ratio",
        "A class has boys and girls in the ratio 3:5, with 32 students total. How many boys and how many girls are there? Explain briefly.",
        [12, 20],
        "Eight parts, four students each: 12 boys and 20 girls.",
    ),
    (
        "choose_pair",
        "A club has 7 members. How many different unordered pairs of members can be chosen? Explain briefly.",
        [21],
        "7 choose 2 = 7*6/2=21.",
    ),
    (
        "percent_change",
        "A quantity increases from 80 to 100. What is the percentage increase relative to the original value? Explain briefly.",
        [25],
        "(100-80)/80*100=25%.",
    ),
    (
        "exponent",
        "Solve 2^(x + 1) = 32 for x. Explain briefly.",
        [4],
        "32=2^5; x+1=5 gives x=4.",
    ),
    (
        "quadratic",
        "Solve x^2 - 5x + 6 = 0 for all real x. Show brief working.",
        [2, 3],
        "(x-2)(x-3)=0 gives x=2 or x=3.",
    ),
    (
        "ages",
        "Ada is twice as old as Ben. In 6 years their ages will sum to 42. How old is each now? Explain briefly.",
        [20, 10],
        "Current sum 42-12=30; 2b+b=30 gives Ben10, Ada20.",
    ),
]

OPEN_REFERENCES = [
    "Amsterdam is the Dutch capital; relevant landmarks include Anne Frank House, Rijksmuseum, Van Gogh Museum, Royal Palace. Avoid Moscow/Greenwich landmark substitutions.",
    "Rayleigh scattering favors shorter wavelengths; blue scatters more than red, violet more than blue; perception helps explain the blue appearance.",
    "Light drives conversion of CO2 and water into sugars, releasing oxygen; chlorophyll absorbs light.",
    "A coherent discussion of trust, empathy, reliability, respect and mutual support; subjective question.",
    "A refrigerant cycle absorbs heat inside and rejects it outside, using compressor work; does not create cold from nothing.",
    "Earth axial tilt changes sunlight angle and day length; distance to the Sun is not the cause of ordinary seasons.",
    "Vaccination primes immune memory and can reduce disease/transmission; coverage can protect others. Avoid guarantees of universal infection prevention.",
    "Weather is short-term atmospheric conditions; climate is longer-term statistical patterns.",
    "Supply and demand describe availability and willingness to buy, with price pressures when either changes, holding other things equal.",
    "Crawling discovers pages, indexing organizes content, retrieval/ranking finds relevant results.",
    "Refraction, internal reflection and dispersion in water droplets separate sunlight into colors.",
    "Right heart pumps blood to lungs; left heart pumps oxygenated blood to body; valves support one-way flow.",
    "Gravity attracts mass toward Earth; avoid attributing ordinary falling to magnetism.",
    "Learning patterns from examples/data to make predictions or decisions, with training and new-data use distinguished.",
    "Exercise can improve cardiovascular fitness, strength, metabolic and mental well-being; avoid cure guarantees.",
    "Evaporation/transpiration, condensation, precipitation and collection/runoff cycle water, powered by sunlight and gravity.",
    "Sleep supports memory, restoration and regulation; avoid claims of a single universally required exact duration.",
    "Renewables replenish on human timescales (sun/wind); finite fuels deplete. Avoid claims of zero environmental impacts.",
    "Roots, fungi and chemical signals can mediate interactions/resources; evidence varies; avoid claiming intentional universal tree-to-tree sharing.",
    "Inflation is a general rise in prices, reducing purchasing power when incomes lag, affecting household budgets differently.",
]


def tasks():
    prompts = [
        s.strip()
        for s in (ROOT / "src/diffusion_lm/generation_prompts.txt")
        .read_text()
        .splitlines()
        if s.strip() and not s.startswith("#")
    ][:20]
    opens = [
        dict(
            id=("amsterdam" if i == 0 else "sky" if i == 1 else f"open_{i+1:02}"),
            category="open",
            prompt=p,
            reference=OPEN_REFERENCES[i],
        )
        for i, p in enumerate(prompts)
    ]
    codes = [
        dict(
            id=name,
            category="code",
            prompt=prompt + CODE_SUFFIX,
            cases=cases,
            function=name,
            forbidden_calls=["sorted", "sort"] if name == "merge_sorted" else [],
        )
        for name, prompt, cases in CODE
    ]
    maths = [
        dict(id=name, category="math", prompt=prompt, answers=answers, reference=ref)
        for name, prompt, answers, ref in MATH
    ]
    rng = random.Random(20261022)
    for group in [opens, codes, maths]:
        dev = set(rng.sample(range(20), 10))
        for i, task in enumerate(group):
            task["split"] = "development" if i in dev else "validation"
    result = [task for group in zip(opens, codes, maths) for task in group]
    assert len(result) == 60 and len({t["id"] for t in result}) == 60
    return result
