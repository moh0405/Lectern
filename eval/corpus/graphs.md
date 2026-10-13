# Graph Algorithms

## Graphs and representations
A graph is a set of vertices connected by edges. Edges can be directed or undirected and may carry weights. An adjacency list stores for every vertex the list of its neighbours and uses space proportional to the number of vertices plus edges, which suits sparse graphs. An adjacency matrix uses a square table and answers the question of whether an edge exists in O(1), but needs space proportional to the number of vertices squared.

## Breadth-first search
Breadth-first search, or BFS, explores a graph level by level from a starting vertex, visiting all vertices at distance one, then all at distance two, and so on. It uses a queue to hold the frontier. Because it discovers vertices in order of distance, BFS finds the shortest path in an unweighted graph. It runs in O(V plus E) time.

## Depth-first search
Depth-first search, or DFS, follows a path as deep as possible before backtracking. It is implemented with recursion or an explicit stack. DFS is used to detect cycles, to find connected components and strongly connected components, and to compute topological orderings. Like BFS it takes O(V plus E) time, but it does not find shortest paths. The key difference between the two is the order of exploration: BFS uses a queue and goes wide, DFS uses a stack and goes deep.

## Dijkstra's algorithm
Dijkstra's algorithm finds the shortest paths from one source to all other vertices in a graph with non-negative edge weights. It repeatedly takes the unvisited vertex with the smallest known distance, using a priority queue, and relaxes the edges leaving it. With a binary heap it runs in O((V plus E) log V). It fails on graphs with negative edge weights.

## Bellman-Ford
The Bellman-Ford algorithm also computes single-source shortest paths but allows negative edge weights. It relaxes every edge V minus 1 times, giving O(V times E) time, and a further pass can detect a negative cycle reachable from the source. It is slower than Dijkstra but more general.

## Topological sort
A topological ordering of a directed acyclic graph lists the vertices so that every edge points from earlier to later. It exists only if the graph has no cycle. It can be computed with a depth-first search that records vertices in reverse finishing order, or with Kahn's algorithm, which repeatedly removes vertices with no incoming edges. It is used for build systems and course prerequisite scheduling.

## Minimum spanning trees and union-find
A minimum spanning tree connects all vertices with the smallest total edge weight. Kruskal's algorithm sorts the edges and adds each one that does not create a cycle, using a union-find structure to test connectivity. Prim's algorithm grows a tree from a start vertex, always adding the cheapest edge that leaves it. Union-find with path compression and union by rank performs operations in nearly constant amortized time.
