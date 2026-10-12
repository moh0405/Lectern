# Sorting Algorithms

## Quicksort
Quicksort picks a pivot element, partitions the array into elements smaller and larger than the pivot, and recursively sorts the two parts. Its average running time is O(n log n) and it sorts in place with small extra space. The worst case is O(n squared), which happens when the pivot is repeatedly the smallest or largest element, for example on already sorted input with a naive first-element pivot. Choosing a random pivot or the median of three makes the worst case very unlikely.

## Merge sort
Merge sort splits the array in half, sorts each half recursively and merges the two sorted halves. It runs in O(n log n) time in every case and is stable, meaning equal elements keep their original relative order. It needs O(n) extra space for the merge step. Its predictable performance and stability make it popular for sorting linked lists and for external sorting of data that does not fit in memory.

## Heapsort
Heapsort builds a max-heap from the array and then repeatedly swaps the root with the last element and sifts down. It is O(n log n) in the worst case, sorts in place and needs only O(1) extra space, but it is not stable and is usually slower in practice than quicksort because of poor cache behaviour.

## Simple quadratic sorts
Insertion sort builds a sorted prefix by inserting each element into place and is O(n squared) in the worst case but O(n) on nearly sorted data, which is why it is used for small subarrays inside hybrid algorithms. Selection sort and bubble sort are also O(n squared) and rarely used in practice.

## Lower bound
Any sorting algorithm that works only by comparing elements needs Omega(n log n) comparisons in the worst case. This follows from a decision tree argument: there are n factorial possible orderings, so a binary decision tree needs at least log2 of n factorial levels, which is about n log n.

## Non-comparison sorts
Counting sort and radix sort avoid comparisons and can beat the n log n bound under assumptions about the keys. Counting sort runs in O(n plus k) when keys are integers in a range of size k. Radix sort sorts numbers digit by digit using a stable sort for each digit and takes O(d times (n plus k)) for d-digit keys.

## Stability and hybrids
A stable sort preserves the order of equal keys, which matters when sorting records by several fields in turn. Real libraries combine ideas: Timsort, used by Python, merges naturally occurring sorted runs and uses insertion sort on short runs, and introsort starts with quicksort and falls back to heapsort if the recursion gets too deep.
