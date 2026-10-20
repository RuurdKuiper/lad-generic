# Saved answers for manual review

150 / 150 answers available.

Configuration IDs are shuffled. Mapping is in review_key.json. Identical answers are grouped within each prompt.

## code_sum_even

Write Python function sum_even(nums) returning the sum of even integers in nums. Handle an empty list. Return only concise Python code, without explanation or examples.

### C01 · 57f6c78d5f20 · visible tokens [42]

````text
```python
from typing import List

from typing import int 
def sum_even(nums):
    return sum(num for num in nums if num % 2 == 0)
```
````

### C02, C07, C08, C09, C10, C15 · 6061848ce58a · visible tokens [42]

````text
Here is the code to solve this problem: 
```python
def sum_even(nums):
    return sum(num for num in nums if num % 2 == 0)
```
````

### C03, C04, C14 · c7386fb08824 · visible tokens [42]

````text
```python
def sum_even(nums):
```python
def sum_even(nums):
    return sum(num for num in nums if num % 2 == 0)
```
````

### C05 · a5ebf2d4e857 · visible tokens [42]

````text
```python
from typing import List

from typing import Optional


def sum_even(nums):
    return sum(num for num in nums if num % 2 == 0)
```
````

### C06 · 0a7d31130373 · visible tokens [72]

````text
Here is the code to solve this problem: 
```python
def sum_even(nums):
    if len(nums) == 0:
    return 0
    sum = 0
    for i in nums:
        if num % 2 == 0:
            sum += num
    return sum
```
````

### C11 · 8d293916bd54 · visible tokens [42]

````text
```python
from typing import List

def int: List:
def sum_even(nums):
    return sum(num for num in nums if num % 2 == 0)
```
````

### C12 · f7d667d58686 · visible tokens [72]

````text
Here is the code to solve this problem: 
```python
def sum_even(nums):
    if len(nums) == 0:
        return 0
    sum = 0
    for num in nums:
        if num % 2 == 0:
            sum += num
    return sum
```
````

### C13 · 67882786deea · visible tokens [54]

````text
Here is the code to solve this problem: 
```python
def sum_even(nums):
    if not nums: 
        return 0
    return sum(num for num in nums if num % 2 == 0)
```
````

## code_palindrome

Write Python function is_palindrome(text) ignoring case and non-alphanumeric characters. Return a boolean. Return only concise Python code, without explanation or examples.

### C01 · 8486641a917d · visible tokens [43]

````text
def is_palindrome(text):
    text = text.lower()
    text = ''..join(c for c in text if c.isalnum())
    return text == text[::-1]
````

### C02 · 1f311a60c67b · visible tokens [32]

````text
def is_palindrome(text):
    text = text.lower() re_sub(text)
    return text == text[::-1]
```
````

### C03, C14 · fe75aae86c05 · visible tokens [31]

````text
def is_palindrome(text):
    text = text.lower().replace_alphanumeric()
    return text == text[::-1]
```
````

### C04 · c3ac20dcef8f · visible tokens [46]

````text
def is_palindrome(text):
    text = text.lower()
_text = ''.join(c for c in text if c.isal() )
    return _text == _text[::-1]
```
````

### C05, C11 · b4543daefd07 · visible tokens [45]

````text
def is_palindrome(text):
    text = text.lower()
    text = ''..join(c for c in text if c.isalnum())
    return text == text[::-1]
```
````

### C06 · 790fc4dea030 · visible tokens [35]

````text
def is_palindrome(text):
    return text == 

def is_palindrome(text):
    return text.lower() == text.lower()
```
````

### C07 · 020bad5dce8f · visible tokens [36]

````text
def is_palindrome(text):
    text = text.lower().replace-r-\Z0-9]',
    return text == text[::-1]
```
````

### C08 · bf93e151fa6f · visible tokens [29]

````text
``` is_palindrome(text):
    return = text.lower(non_al(text).isal()
```return True
```
````

### C09 · e03b5fbf7935 · visible tokens [32]

````text
def is_palindrome(text):
    text = re.sub(r_alnum, text
    return text == text[::-1]
```
````

### C10 · 41e87d8e8c6b · visible tokens [32]

````text
def is_palindrome(text):
    text = text.lower().replace_join(text)
    return text == text[::-1]
```
````

### C12 · c678584132fc · visible tokens [35]

````text
def is_palindrome(text):
    text = re.sub(r_non_al)
    return text.lower() == text.lower()
```
````

### C13 · e8bcb5e4d35a · visible tokens [55]

````text
Here is the code to solve this problem: 
```python
def is_palindrome(text):
    text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return text.lower[::-1]
```
````

### C15 · 868b086bbfd3 · visible tokens [46]

````text
def is_palindrome(text):
    return True
```
def is_palindrome(text):
    text = text.lower().replace-zA-Z0
    return text == text[::-1]
```
````

## code_fibonacci

Write Python function fibonacci(n) returning a list of the first n Fibonacci numbers, starting with 0, 1. For n <= 0 return []. Return only concise Python code, without explanation or examples.

### C01, C05, C11 · 4914da59486e · visible tokens [66]

````text
```python
def fibonacci(n):
    if n <= 0:
        return []
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib
```
````

### C02 · f14a379abe8c · visible tokens [83]

````text
```python
def fibonacci(n):
    if n <=  or fibonacci(n):
        return []
    a = 0
    b = 1
    fib = [0]
    for i in range(1, n):
        b = b*b
        a = b = a + b
        fib.append(b)
    return fib
```
````

### C03 · 76d91750857c · visible tokens [29]

````text
```python
def fibonacci(n):
    if n:
        return(n)
    else:
        return []
```
````

### C04 · 926c846a9f81 · visible tokens [31]

````text
```python
def fibonacci(n):
    if n:
        return(0)
    else:
        return(1)
```
````

### C06 · 3d904e48decc · visible tokens [76]

````text
```python
from typing import List

def fibonacci(n):
def fibonacci(n):
    if n <= 0:
        return []
    fib = = [0, 1]
    for i in range(2, n):
        fib.append(fib[i] + fib[i-1])
    return fib
```
````

### C07, C09 · bdb326454135 · visible tokens [77]

````text
Here is the code to solve this problem: 
```python
def fibonacci(n):
    if n <= 0:
        return []
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib
```
````

### C08 · 359116bfbf17 · visible tokens [68]

````text
```python
def fibonacci(n):
    if n <=  or fibonacci(n):
        return []
    else =0, 1 = [0        for i in range(2, n):
        fib.append(fib[i] + fib[i-1])
    return fib
```
````

### C10 · 0721d5b9f4b3 · visible tokens [41]

````text
```python
def fibonacci(n):
    if n <= return fibonacci(n):
        return []
    else: 0, 1 + fibonacci(n(1))
```
````

### C12 · 13aacaeda0c4 · visible tokens [77]

````text
```python
from typing import List

def fibonacci(n):
def fibonacci(n):
    if n <= 0:
        return []
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib
```
````

### C13 · 991d9ab35af4 · visible tokens [75]

````text
Here is the code to solve this problem: 
```python
def fibonacci(n):
    if n <= 0:
        return []
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i] + fib[i-1])
    return fib
```
````

### C14 · 8bc89c17fe7c · visible tokens [31]

````text
```python
def fibonacci(n):
    if n:
        return(n)
    else:
        return [0]
```
````

### C15 · 489ee29f1835 · visible tokens [77]

````text
Here is the code to solve this problem: 
```python
def fibonacci(n):
    if n <= 0:
        return []
    fib = [0, 1]
    for i range(2, n):
        fib.append(fib[i] + fib1])
        i += 1
    return fib
```
````

## code_deduplicate

Write Python function deduplicate(items) removing duplicates while preserving first occurrence order. Items are hashable. Return only concise Python code, without explanation or examples.

### C01, C05 · 65027643285e · visible tokens [57]

````text
```python
def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
```
````

### C02, C08 · 760a1aa47094 · visible tokens [68]

````text
``` deduplicate
from collections import OrderedDict
import collections = OrderedDict
def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
```
````

### C03 · 3c6c0290fcac · visible tokens [37]

````text
```python
def deduplicate(items):
    seen = set()
    (items)
    return [item for item in items if not item in seen]
```
````

### C04 · fff26c75fed0 · visible tokens [40]

````text
```python
def deduplicate(items):
    seen = set()
    (items)
    return [item for item in items if not not seen.add(item)]
```
````

### C06 · 159587adb216 · visible tokens [49]

````text
```python
def deduplicate(items):
    result:
    seen = set() 
    for item in items:
        if item not in seen:
            seen.add(item)
    return result
```
````

### C07 · 14c7c07ebc32 · visible tokens [68]

````text
Here is the code to solve this problem: 
```python
def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
```
````

### C09 · 16f1e01a88ec · visible tokens [44]

````text
```python
from typing import List, set()
```python
def deduplicate(items):
    seen = set(items)
    return [item for item in items if item in seen]
```
````

### C10 · 5b0da22997c4 · visible tokens [68]

````text
```python
from collections import deque

from collections import deque 
def deduplicate(items):
    seen = set()
    result = deque()
    for item in items:
        if item not seen:
            result.append(item)
            seen.add(item)
    return result
```
````

### C11 · cf25f3157a66 · visible tokens [42]

````text
```python
def deduplicate(items):
    return []
    for item in items:
        if item not in seen:
            seen.append(item)
    return result
```
````

### C12 · e4a142c48bee · visible tokens [22]

````text
```python
from collections import OrderedDict

deduplicate(items):
    return list(items)
```
````

### C13 · b117f9abeacb · visible tokens [67]

````text
```python
from collections import defaultdict
    seen = set()
def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item not seen:
            seen.add(item)
            result.append(item)
    return result
```
````

### C14 · f9dbdff5fab4 · visible tokens [37]

````text
```python
def deduplicate(items):
    seen = set(map((items))
    return [item for item in items if item not in seen]
```
````

### C15 · 60cee29dc4ad · visible tokens [29]

````text
Here is the code to solve this problem: 
```python
def deduplicate(items):
    return set(items)
```
````

## code_balanced

Write Python function balanced(s) checking balanced parentheses (), brackets [], and braces {}. Ignore other characters. Return only concise Python code, without explanation or examples.

### C01 · 7aed4f66864e · visible tokens [80]

````text
```python
def balanced(s):
    stack = []
    brackets = {
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack and stack[-1] == brackets:
                stack.pop()
            else:
                return False
    return not stack
```
````

### C02 · 5a187fb78848 · visible tokens [85]

````text
```
from collections import defaultdict

def balanced(s):):
def balanced(s):
    stack = []
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack and stack[-1] == brackets:stack.pop()
            else:
                return False
    return not stack stack
```
````

### C03 · 1ec74e5940e9 · visible tokens [98]

````text
```python
def balanced(s):
    stack = []
    brackets = {
        ')': '(', ']']': '[', '}'}': '{'}
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack and stack[-1] == brackets[char]:
                stack.pop()
            else:
                return False
    return not stack
```
````

### C04 · e2aafa229535 · visible tokens [98]

````text
```
def balanced(s):
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    
    for char in s:
        if char in pairs:
            stack.append(char)
        elif char in pairs.values():
            if stack and stack[-1] == pairschar:
                stack.pop()
            else:
                return False
    
    return not stack
```
````

### C05 · 23b8d4fcfaef · visible tokens [72]

````text
```python
def balanced(s):
    stack = []
    brackets = {}
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if not stack or stack.pop() != brackets[:
                return False
    return not stack
```
````

### C06 · d3792c32e572 · visible tokens [74]

````text
```python
def balanced(s):
    stack = []
    pairs = set()
    for char in s:
        if char in pairs:
            stack.append(char)
        elif char in stack:
            stack.pop()
        else:
            return False
    return len(stack) == 0
```
````

### C07 · 62d27cd201f2 · visible tokens [82]

````text
Here is the code to solve this problem: 
```python
def balanced(s):
    stack = []
    result = True
    for char in s:
        if char in stack:
            stack.append(char)
        elif char in stack:
            stack.pop()
        else:
            result = False
    return len(stack)
```
````

### C08 · 5a2d9d476b44 · visible tokens [82]

````text
```
from collections import defaultdict

def balanced(s):):
def balanced(s):
    stack = []
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack stack stack[-1]:
                return False
            stack.pop()
)
    return not stack stack
```
````

### C09 · b7f790221559 · visible tokens [81]

````text
Here is the code to solve this problem: 
```python
def balanced(s):
    stack = []
    brackets = {'}
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack.pop() != brackets[char]:
                return False
    return not stack```
````

### C10 · 996edc8ffa2e · visible tokens [55]

````text
```python
def balanced(s): 
    stack=[]
        for(s):
        if char in s:
            stack.append(char)
        elif char in stack:
            stack.pop(char)
    return True
```
````

### C11 · 1b598bcd85c8 · visible tokens [80]

````text
```python
def balanced(s):
    stack = []
    brackets = {
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack and stack[-1] == char:
                stack.pop()
            else:
                return False
    return not stack
```
````

### C12 · b5e08021c4f6 · visible tokens [88]

````text
```python
def balanced(s):
    stack = []
    brackets = {')
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack.pop() != brackets[char]:
                return False
        else:
            return False
    if not stack:
        return True
    return False
```
````

### C13 · 9975495b6ea8 · visible tokens [73]

````text
```python
def balanced(s):
    stack = []
    brackets = {}
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets:
            if stack.pop():
                return True
            else:
                return False
    return not stack
```
````

### C14 · feb0dee529df · visible tokens [91]

````text
```
def balanced(s):
    stack = []
    pairs = {
        ')': '(',
        ']': '[',
        '}': '{'}
    }    for in s:
        if char in pairs:
            stack.append(char)
        elif char in pairs:
            if pairs[ stack[-1] != char:
                stack.pop()
    return stack == []
```
````

### C15 · 37a62799a075 · visible tokens [93]

````text
```python
from collections import defaultdict

pairs = {
}

def balanced(s):
    stack = []
    for char in s:
        if char in pairs:
            stack.append(char)
        elif char in pairs:
            if stack.pop()
                 != char:
                return False
            else:
                return False
    if not stack:
        return True
    else:
```
````

## code_binary_search

Write Python function binary_search(nums, target) for sorted nums, returning its index or -1 if absent. Return only concise Python code, without explanation or examples.

### C01, C05 · 1a0c10a07b2e · visible tokens [119]

````text
Here is the code to solve this problem: 
```python
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            left = mid
            right = mid - 1
        elif nums[mid] < target:
            right = mid - 1
        else:
            left = mid + 1
    return -1
```
````

### C02 · 6c2b2700f4f2 · visible tokens [37]

````text
def binary_search(nums, target):
    return None
def binary_search(nums, target):
    return -(nums(nums) - target)
```
````

### C03, C04, C14 · dd935ce96bc0 · visible tokens [93]

````text
Here is the code to solve this problem: 
```python
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid]
            left = mid + 1
        else:
            right = mid - 1
    return -1
```
````

### C06 · 3ac48f4bf1c2 · visible tokens [107]

````text
def binary_search(nums, target):
    return None
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            result = mid
        elif nums[mid] < target:
            left = mid
        else:
            right = mid - 1
    return result
```
````

### C07 · 06a2b895a54d · visible tokens [93]

````text
Here is the code to solve this problem: 
```python
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[ target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
```
````

### C08 · 0f6525484742 · visible tokens [58]

````text
def binary_search(nums, target):
    return -
def binary_search(nums, target):
    return -
def binary_search(nums,, target target):
    return -
def binary_search(nums, target):
    return -

````

### C09 · 74df1c5fd632 · visible tokens [98]

````text
def binary_search(nums, target):
    left = 0
_right = len(nums) - 1
    while left <= right:
        mid = (left + _right) // 2
        if nums[mid] < target:
            left = mid + 1
        elif nums[mid] > target:
            _right = mid - 1
        else:
            return mid
    return -1
```
````

### C10 · 67aaa6210dfa · visible tokens [35]

````text
def binary_search(nums, target):
    return None
def binary_search(nums, target):
    return sorted(nums)
```python
```
````

### C11 · 264f54813759 · visible tokens [118]

````text
Here is the code to solve this problem: 
```python
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            left = mid
            right = mid - 1
        elif nums[mid] < target:
            right = mid - 1
        else:
            left = mid + 1
    return left
```
````

### C12 · a3ae94e4fce1 · visible tokens [87]

````text
def binary_search(nums, target):
    else:
        mid_index = len(nums) // 1
        if nums[mid_index] == target:
            return mid_index
        elif nums[mid_index] < target:
            return mid_index - 1
        else:
            mid_index = mid_index + 1
    return result
```
````

### C13 · 8aa9fd893ad1 · visible tokens [107]

````text
Here is the code to solve this problem: 
```python
def binary_search(nums, target):
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            result = mid
        elif nums[mid] < target:
            left = mid
        else:
            right = mid + 1
    return result
```
````

### C15 · d6cc8b6b0700 · visible tokens [51]

````text
def binary_search(nums, target):
    left
    def binary_search(nums, target):
    return left if nums == target else binary_search(nums)
    return binary_search(nums, target)
```
````

## code_word_counts

Write Python function word_counts(text) returning a dictionary of word frequencies. Split on whitespace and ignore case. Return only concise Python code, without explanation or examples.

### C01, C05 · 4611ac59c867 · visible tokens [47]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split().lower())
    counts = dict(Counter(words))
    return counts
```
````

### C02 · 22fc7c115308 · visible tokens [43]

````text
def word_counts(text):
    return = {}

def word_counts(text):
    words = text.split()
    result = {}(words)
    return result
```
````

### C03 · b3a65bf51742 · visible tokens [48]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split().lower())
    counts = Counter(words)
    return dict(counts)
```
````

### C04 · 1cb0893728ad · visible tokens [72]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.lower()
    words = words.split()
    counts = {}(words)
    for word in words:
        counts[word] += counts.get] + 1
    return counts
```
````

### C06 · 8e4b08d7db78 · visible tokens [52]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split()
    count = Counter(word for word in words.lower())
    return dict(counts)
```
````

### C07 · 2fa7a39d59df · visible tokens [48]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.lower().split()
    counts = Counter(words)
    return dict(counts)
```
````

### C08 · 2c9f01791ba4 · visible tokens [42]

````text
def word_counts(text):
    return = {}()
def word_counts(text):
    text = text(split).lower()
    for = dict(text)
    return
````

### C09 · ef7166805ccb · visible tokens [61]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split().lower()
    counts = dict(words)
    for word in words:
        counts[word] += 1
    return counts
```
````

### C10 · 072cfe4efc9d · visible tokens [68]

````text
def word_counts(text):
    return dict() 
def word_counts(text):
    c = Counter(lower.split(text))
    return dict(c)
    def word_counts(text):
    c = Counter(lower.split())
    return dict(c)
```
````

### C11 · bbf86f92dbb8 · visible tokens [78]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split().lower())
    counts = {}
    for word in words:
        if word in counts:
            counts[word] = 1
        else:
            counts[word] += 1
    return counts
```
````

### C12 · ae532b92ab0d · visible tokens [48]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split()
    count = Counter(words.lower())
    return dict(counts)
```
````

### C13 · 1081789071f5 · visible tokens [46]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.split()
    count = Counter(words)
    return dict(count)
```
````

### C14 · 31cf0286e8bc · visible tokens [67]

````text
Here is the code to solve this problem: 
```python
def word_counts(text):
    words = text.lower()
    words = words.split()
    counts = {}(words)
    for word in words:
        counts[word] += 1
    return counts
```
````

### C15 · fa6a8175ea6f · visible tokens [72]

````text
def word_counts(text):
    words = text.split()word_counts = {}  
    for word in words:
        if word in word__counts:
            word_counts[word] += 1
        else:
            word_counts[word] = 1
    return word_counts
```
````

## code_merge_sorted

Write Python function merge_sorted(a, b) merging two sorted integer lists into one sorted list. Do not call sorted() or .sort(). Return only concise Python code, without explanation or examples.

### C01 · 51ee7f92ee1d · visible tokens [122]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result += a[i:]
    result += b[j:]
    return result
```
````

### C02 · ede6e77cd54b · visible tokens [128]

````text
```python
def merge_sorted(b):
```python
def merge_sorted(a, b):
    result = []
    i = 0    while j = 0
        while i < len(a) and j < len(ab)
            a[i] < b[j]:
                result.append(a[i])
                i += 1
        result.appendappend(b[j])
        j += 1
    while i < len(a):
        result.append(a[i])
        i 1
    while
````

### C03 · 52e0985b7b62 · visible tokens [128]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = 0    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result

````

### C04 · 1da2b4d29cff · visible tokens [122]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result. a[i:]
    result. b[j:]
    return result
```
````

### C05 · b2d0d1bdeb38 · visible tokens [124]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    return result + list(a[i:]) + list(b[j:])
```
````

### C06 · 6055faa17e1d · visible tokens [74]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    for i in range(len(a)):
        result.append(a[i])
    for i in range(len):
        result.append(b[i])
    return result
```
````

### C07, C13 · 814266b77872 · visible tokens [128]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i, j = 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result

````

### C08 · dbe614a87cd2 · visible tokens [75]

````text
```python
def merge_sorted(b):
```python
def merge_sorted(a, b):
    result = []
    i =  =        while = True
    while =
        result =append(min[i])
        i += 1
    result.append(b)b])
    return result
```
````

### C09 · 2f4cedb704d8 · visible tokens [123]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend((a)
    result.extend(b)
    return result
```
````

### C10 · 8bd5a20f417d · visible tokens [99]

````text
```python
def merge_sorted(b):
```python
def merge_sorted(a, b):
    result = []
    for i = 0, < len(a):
        if a(i] < b[0]:
            result.append(a[i])
        else:
            result.append(b[0])
            b.pop(0)
    result.extend(b)
    return result
```
````

### C11 · b25eb23a2a18 · visible tokens [128]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result
````

### C12 · 555abd58eb4b · visible tokens [128]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = 
    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
````

### C14 · 715065ffd98c · visible tokens [128]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
    i = 0    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while result < len(a):
        result.append(a[i])
        i += 1
````

### C15 · 0433b033dfb3 · visible tokens [123]

````text
Here is the code to solve this problem: 
```python
def merge_sorted(a, b):
    result = []
        i = j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while result:
        resultresult.append(result.pop())
    return result
```
````

## code_flatten

Write Python function flatten(rows) flattening a list of lists by one level. Preserve order and handle empty lists. Return only concise Python code, without explanation or examples.

### C01, C05, C11 · bc12bcc42966 · visible tokens [24]

````text
```python
def flatten(rows):
    return [item for row in rows for item in row]
```
````

### C02, C14 · 5e0bad9a739b · visible tokens [35]

````text
```python
from typing import List

def flatten: List]
def flatten(rows):
    return [item for row in rows for item in item]
```
````

### C03 · ae5bd1fdfa26 · visible tokens [35]

````text
```python
from typing import List

def int: List:
def flatten(rows):
    return [item for row in rows for item in item]
```
````

### C04 · 13510bb27c28 · visible tokens [35]

````text
```python
from typing import flatten

from typing import List 
def flatten(rows):
    return [item for sub in rows for item in sub]
```
````

### C06 · 190b3711e3ef · visible tokens [33]

````text
```python
from typing import List

def flatten_list):
def flatten(rows):
    return [item for row in row in rows]
```
````

### C07, C13 · 4b55ac3da278 · visible tokens [35]

````text
Here is the code to solve this problem: 
```python
def flatten(rows):
    return [item for row in rows for item in row]
```
````

### C08 · 774c15f1e5ee · visible tokens [35]

````text
```python
from typing import List

def flatten: List]
def flatten(rows):
    return [item for sub in rows for item in item]
```
````

### C09, C12 · 44a7543bfdfd · visible tokens [35]

````text
Here is the code to solve this problem: 
```python
def flatten(rows):
    return [item for row in rows for item in item]
```
````

### C10 · 926fe8fc0670 · visible tokens [39]

````text
```python
from collections import deque
from collections import deque()
def flatten(rows):
    return [item for row in enumerate(rows) for item, in row]
```
````

### C15 · df7c3ec93985 · visible tokens [35]

````text
Here is the code to solve this problem: 
```python
def flatten(rows(rows):
    return [item(item for item in rows]
```
````

## code_fizzbuzz

Write Python function fizzbuzz(n) returning strings for integers 1 through n: Fizz for multiples of 3, Buzz for 5, FizzBuzz for both, otherwise the number as a string. Return only concise Python code, without explanation or examples.

### C01 · c2d926dfa05c · visible tokens [53]

````text
```python
def fizzbuzz(n):
    return ['Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else str(i) for i in range(1, n+1)]
```
````

### C02 · aec1e1cce928 · visible tokens [96]

````text
```python
from typing import List

from typing import List 
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Buzz' if i % 5 == 0 else 'Buzz' if i % 3 == 0 else 'Fizz' if i % 3 == 0 else 'Fizz' i in range(1, n+1)]
```
````

### C03 · 6eecbb1cb8e5 · visible tokens [89]

````text
```python
from typing import List

from typing import List 
def fizzbuzz(n):
    return [i if i % gcd(3, 5) != 0 else 'Fizz' if i % 3 0 else 'Buzz' if i % 5 == 0 else 'Fizz' if i % 3 == 0 else i for i in range(1, n + 1)]
```
````

### C04 · 1c9b1a3ff25a · visible tokens [88]

````text
```python
from functools import reduce

def solution(n):

def fizzbuzz(n):
    return [str(i) if i % 15 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' i in range(1, n+1)]
```
````

### C05, C11 · 0f28e4398d44 · visible tokens [75]

````text
```python
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else 'FizzBuzz' for i in range(1, n+1)]
```
````

### C06 · bb176ed70ad9 · visible tokens [82]

````text
```python
from typing import List

def int(n):
def fizzbuzz(n):
    return [str(i) i % 1 333, 15 * 1, 10, 15 * 1, 15 * 1] + 
(i % 1) for i in range(1, n)]
```
````

### C07 · d5e89dcba91e · visible tokens [76]

````text
Here is the code to solve this problem: 
```python
def fizzbuzz(n):
    return [i for i in range(1, n+1) if i % 3 == 0 and i % 5 == 0 else i % % 3 == 0 else i % 5 == 0 else str(i)]
```
````

### C08 · 088cf0a01fa6 · visible tokens [83]

````text
```python
from typing import List

from typing import List 
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if 3 % 3 == 0 else 'Buzz' if i % 5 == 0 else 'FizzBuzz for i i in range(1)]
```
````

### C09 · 13d1eae62f56 · visible tokens [81]

````text
```python
from typing import List
from typing import List


def fizzbuzz(n):
    return [join ''. for i in range(1, n+1)
         + 3*' + ' ' if i % 3 == 0 else ''
         + 'Buzz' if i % 5 == 0 else ''
         + str(i)
```
````

### C10 · bcaf96a67052 · visible tokens [86]

````text
```python
from typing import List

def int: List:
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else 'Fizz' for i in range(1, n + 1)]
```
````

### C12 · e79acc9bcd7f · visible tokens [75]

````text
```python
from typing import List

def int(n):
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if i % 30 == 00 else 'Buzz' for i in range(1, n+1)]
```
````

### C13 · 71c573f5ee3b · visible tokens [77]

````text
```python
from typing import List
from typing import List
    def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if i % 3 == 0 0 else str(i) for i in range(1, n + 1)]
```
````

### C14 · 6da8224dbd36 · visible tokens [87]

````text
```python
from typing import List

from typing import List 
def fizzbuzz(n):
    return [str(i) if i % 3 != 0 and i % 5 != 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else 'Fizz' else i for in range(1, n+1)])]
```
````

### C15 · 4dc322e088f8 · visible tokens [128]

````text
```python
def fizzbuzz(n): 
```python
def fizzbuzz(n):
    return [i for i in range(n) if i % 33000 == 000000000 or i 5000 == 00000 else i % 1000 == 000 else 0000 else 00000000000000000000000000000000000000000
````
