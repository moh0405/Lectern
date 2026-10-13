# Trees and Heaps

## Binary trees and traversals
A binary tree is a hierarchical structure in which each node has at most two children, called left and right. A tree can be traversed in several ways. Inorder traversal visits the left subtree, then the node, then the right subtree. Preorder visits the node first and postorder visits it last. Level-order traversal visits nodes one depth at a time using a queue.

## Binary search trees
A binary search tree keeps the invariant that every key in a node's left subtree is smaller than the node's key and every key in its right subtree is larger. Searching, inserting and deleting take time proportional to the height of the tree. An inorder traversal of a binary search tree produces the keys in sorted order. If keys are inserted in sorted order the tree degenerates into a linked list of height n and operations become O(n).

## Balanced trees
Self-balancing trees guarantee a height of O(log n). An AVL tree keeps the heights of the two subtrees of every node within one of each other and restores the balance with rotations after an insertion or deletion. A red-black tree uses node colours and looser rules, which gives slightly taller trees but fewer rotations. Standard library ordered maps are usually built on red-black trees.

## Heaps and the heap property
A binary heap is a complete binary tree that satisfies the heap property. In a min-heap every parent is smaller than or equal to its children, so the smallest element is always at the root. A max-heap is the reverse. Because the tree is complete it can be stored compactly in an array, where the children of index i are at 2i plus 1 and 2i plus 2.

## Heap operations and priority queues
Inserting into a heap appends the new element at the end and sifts it up until the heap property is restored, which takes O(log n). Removing the minimum swaps the root with the last element, removes it, and sifts the new root down, also O(log n). Building a heap from n elements takes only O(n) with the bottom-up method. Heaps are the standard implementation of a priority queue, which always serves the element with the highest priority first.

## Tries
A trie, or prefix tree, stores strings by sharing common prefixes. Each edge represents a character and each path from the root spells a prefix. Looking up a word of length m takes O(m) regardless of how many words are stored, which makes tries ideal for autocomplete and spell checking.
