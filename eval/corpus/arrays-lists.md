# Arrays and Linked Lists

## Arrays
An array stores elements in contiguous memory, which makes access by index O(1) because the address of element i is the base address plus i times the element size. Inserting or deleting in the middle of an array requires shifting every later element, which costs O(n). Arrays have excellent cache locality, so scanning them is very fast on real hardware.

## Dynamic arrays
A dynamic array such as a Python list or a C++ vector grows automatically. When the underlying buffer is full it allocates a larger one, usually twice the size, and copies the elements across. Appending is therefore O(1) amortized, while inserting at the front is O(n). Removing from the end is O(1).

## Singly linked lists
A linked list is a chain of nodes, where each node holds a value and a pointer to the next node. A singly linked list can only be traversed in one direction. Inserting or deleting right after a node you already hold a reference to is O(1), because only pointers change, but finding the k-th element requires walking k nodes, which is O(k). There is no random access.

## Doubly linked lists
A doubly linked list stores both a next and a previous pointer in every node. This allows traversal in both directions and makes deleting a node O(1) when you hold a pointer to it, since you can reach its predecessor directly. The price is extra memory for the second pointer and more pointer updates on every insertion.

## Choosing between them
Use an array or dynamic array when you need fast indexed access and mostly append at the end. Use a linked list when you frequently insert and remove at known positions and never need indexing. In practice dynamic arrays win more often than the textbook complexity suggests, because contiguous memory is friendly to the CPU cache and linked nodes are scattered across the heap.

## Stacks and queues
A stack is a last-in first-out structure with push and pop operations, used for undo history, expression evaluation and depth-first traversal. A queue is first-in first-out with enqueue and dequeue, used for scheduling and breadth-first traversal. Both can be built on a dynamic array or a linked list, and a double-ended queue or deque supports efficient insertion and removal at both ends.
