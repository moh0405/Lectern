# Memory Management in Programs

## The call stack
The call stack is a region of memory that stores one stack frame for every active function call. A frame holds the function's local variables, its parameters and the return address. Frames are pushed when a function is called and popped when it returns, so allocation and deallocation are extremely fast. The stack has a fixed limit, and recursion that goes too deep causes a stack overflow.

## Heap memory
Heap memory is the region used for dynamic allocation, where objects can be created at runtime and live until they are freed. Unlike the stack, heap allocations are not tied to function calls, so an object can outlive the function that created it. Allocating from the heap is slower because the allocator must find a free block, and long-running programs can suffer from fragmentation, where free memory is split into pieces too small to use.

## Manual memory management
In languages such as C, the programmer allocates heap memory with malloc and releases it with free. Forgetting to free memory causes a memory leak, freeing it twice causes a double free, and using memory after freeing it is a use-after-free bug. These errors are a major source of crashes and security vulnerabilities.

## Garbage collection
Garbage-collected languages such as Java, Go and Python reclaim unreachable heap objects automatically. Reference counting frees an object as soon as its count drops to zero but cannot reclaim cycles on its own. Tracing collectors, such as mark-and-sweep, start from the roots, mark everything reachable and sweep away the rest. Generational collectors exploit the observation that most objects die young.

## Virtual memory and paging
Virtual memory gives each process its own address space, which the operating system maps onto physical memory in fixed-size pages. When a program touches a page that is not resident, a page fault occurs and the operating system loads it from disk. Paging allows programs to use more memory than is physically installed, but heavy paging, called thrashing, slows the machine dramatically.

## Cache hierarchy
Modern processors keep recently used data in small fast caches, so programs with good locality of reference run much faster. Spatial locality means accessing nearby addresses, which is why scanning an array is fast, and temporal locality means reusing recently touched data.
