# Hash Tables

## The idea
A hash table stores key-value pairs and supports insertion, lookup and deletion in O(1) time on average. A hash function converts a key into an integer, and that integer is reduced modulo the table size to choose a bucket. Because the bucket is found by computation rather than by searching, the cost does not grow with the number of stored items as long as the table is kept sparse enough.

## Collisions
Two different keys can hash to the same bucket, which is called a collision. Collisions are unavoidable by the pigeonhole principle whenever there are more possible keys than buckets, so every hash table needs a collision resolution strategy.

## Separate chaining
In separate chaining each bucket holds a linked list, or another small collection, of all entries that hashed there. A lookup computes the bucket and then scans its chain. With a good hash function the chains are short, and the expected cost is O(1 plus the load factor). In the worst case, when every key lands in one bucket, the table degrades to O(n).

## Open addressing
Open addressing stores every entry directly in the array and resolves a collision by probing for another free slot. Linear probing tries the next slot, quadratic probing tries slots at growing offsets, and double hashing uses a second hash function to choose the step. Deletion is subtle because removing an entry can break probe sequences, so implementations use tombstone markers. Open addressing is cache friendly but its performance falls sharply as the table fills up.

## Load factor and resizing
The load factor is the number of stored entries divided by the number of buckets. When it grows past a threshold, commonly 0.75 for chaining, the table is resized to roughly twice as many buckets and every entry is rehashed. Resizing is expensive but happens rarely, so insertion remains O(1) amortized.

## Good hash functions
A good hash function spreads keys uniformly across buckets and is deterministic and fast. Using a table size that is a prime number helps when keys follow patterns. Hash tables do not keep keys in sorted order, so if you need ordered iteration or range queries a balanced search tree is a better fit.
