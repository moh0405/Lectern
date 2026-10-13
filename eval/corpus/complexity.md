# Algorithm Analysis and Complexity

## Big-O notation
Big-O notation describes an upper bound on how the running time or memory use of an algorithm grows as the input size n grows. When we say an algorithm is O(n squared), we mean its cost grows no faster than a constant times n squared for large inputs. Constant factors and lower-order terms are ignored, so 3n squared plus 10n plus 7 is simply O(n squared). Big-O is most often used to describe the worst case, but it is only a bound: it says nothing by itself about whether the bound is tight.

## Omega and Theta
Big-Omega gives a lower bound and Big-Theta gives a tight bound. An algorithm whose running time is Theta(n log n) is both O(n log n) and Omega(n log n), which means it grows exactly at that rate up to constant factors. Merge sort is Theta(n log n) in every case, while insertion sort is O(n squared) in the worst case but Omega(n) on input that is already sorted.

## Amortized analysis
Amortized analysis averages the cost of a sequence of operations rather than looking at a single operation in isolation. A dynamic array that doubles its capacity when full has an expensive append every so often, because all elements must be copied, but the total cost of n appends is O(n). Each append therefore costs O(1) amortized, even though one individual append can cost O(n). The same reasoning, often done with the accounting method or the potential method, explains why incrementing a binary counter is cheap on average.

## Recurrences and the master theorem
Divide-and-conquer algorithms are analysed by writing a recurrence such as T(n) = 2T(n/2) + O(n) for merge sort. The master theorem solves recurrences of the form T(n) = aT(n/b) + f(n) by comparing f(n) with n raised to the power log base b of a. In merge sort a is 2 and b is 2, so the two sides are balanced and the solution is Theta(n log n). Binary search has T(n) = T(n/2) + O(1), which solves to O(log n).

## Space complexity
Space complexity counts the extra memory an algorithm needs beyond its input. Recursive algorithms use stack space proportional to the recursion depth, so a naive recursive traversal of a degenerate tree with n nodes needs O(n) stack space. In-place algorithms such as heapsort use O(1) extra space, while merge sort needs O(n) auxiliary space for merging.
