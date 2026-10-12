# Dynamic Programming and Greedy Algorithms

## Dynamic programming
Dynamic programming solves a problem by breaking it into overlapping subproblems and storing each answer so it is computed only once. It applies when a problem has optimal substructure, meaning an optimal solution is built from optimal solutions of its subproblems, and overlapping subproblems, meaning the same subproblem recurs many times. Computing Fibonacci numbers naively takes exponential time, but caching each value reduces it to O(n).

## Memoization and tabulation
There are two styles. Memoization is top-down: write the natural recursion and cache results in a dictionary or array. Tabulation is bottom-up: fill a table iteratively starting from the base cases, so no recursion is needed. Tabulation avoids recursion depth limits and can often reduce memory by keeping only the last row or two of the table.

## The knapsack problem
In the 0/1 knapsack problem each item has a weight and a value, and we want the most valuable set of items that fits within a weight capacity. The table entry for item i and capacity w is the better of skipping item i or taking it and adding its value to the best result for the remaining capacity. This runs in O(n times W) time, which is pseudo-polynomial because it depends on the numeric value of the capacity.

## Longest common subsequence and edit distance
The longest common subsequence of two strings is found by a table indexed by prefixes of both strings: if the last characters match the answer extends the diagonal entry, otherwise it is the larger of the entries above and to the left. Edit distance, also called Levenshtein distance, counts the fewest insertions, deletions and substitutions needed to turn one string into another and uses the same kind of table with O(m times n) time.

## Greedy algorithms
A greedy algorithm builds a solution by always making the locally best choice and never reconsidering it. Greedy methods are fast and simple but are only correct when the problem has the greedy-choice property. Interval scheduling is a classic example: sorting activities by earliest finish time and repeatedly taking the next compatible one yields a maximum set of non-overlapping activities.

## Huffman coding
Huffman coding builds an optimal prefix code for data compression. It repeatedly merges the two least frequent symbols using a min-heap, so frequent symbols end up with short codes and rare symbols with long codes. Greedy fails for the 0/1 knapsack and for coin change with arbitrary denominations, where dynamic programming is required.
