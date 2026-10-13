# Python Notes

## Lists, tuples and deques
A Python list is a dynamic array: indexing is O(1) and appending is O(1) amortized, but inserting or popping at the front is O(n). A tuple is an immutable sequence and can be used as a dictionary key. For queues use collections.deque, which supports O(1) appends and pops at both ends.

## Dictionaries and sets
A Python dict is a hash table. Since Python 3.7 dictionaries preserve insertion order. Keys must be hashable, which is why lists cannot be used as keys. A set is an unordered collection of unique hashable elements with average O(1) membership tests.

## Generators and iterators
A generator function uses the yield keyword to produce values lazily, one at a time, keeping its local state between calls. This makes it possible to process sequences larger than memory. Generator expressions have the same lazy behaviour with a compact syntax.

## Decorators
A decorator is a function that takes another function and returns a modified version of it, applied with the at-sign syntax above a function definition. Decorators are used for logging, caching, access control and timing. The functools.lru_cache decorator memoizes a function's results, which is a convenient way to write top-down dynamic programming.

## The GIL and concurrency
CPython has a global interpreter lock, the GIL, which lets only one thread execute Python bytecode at a time. Threads therefore do not speed up CPU-bound work, although they still help with input and output waiting. For CPU-bound parallelism use the multiprocessing module, and for many concurrent network connections use asyncio.

## Mutability pitfalls
Using a mutable object such as a list as a default argument value is a classic bug, because the default is created once when the function is defined and shared across all calls. Assignment never copies an object; to copy a nested structure use copy.deepcopy.
