---
title: "Graph Traversal Algorithms: BFS and DFS"
author: "Dorothy Gale, Huckleberry Finn"
date: "January 5, 2025"
---

**Department of Computer Science, Emerald City Technical Institute**

# Abstract

Graph traversal algorithms systematically visit vertices in a graph. This paper examines the two fundamental approaches: Breadth-First Search (BFS) explores level-by-level, while Depth-First Search (DFS) explores as deep as possible before backtracking. Understanding their distinct characteristics is essential for selecting the appropriate algorithm for path-finding, connectivity analysis, and graph-based problem solving.

*Example paper made with Markdown + Pandoc for Scroll Press.*

# Graph Fundamentals

A graph $G = (V, E)$ consists of vertices $V$ and edges $E$ connecting pairs of vertices. **Graph traversal** visits all vertices systematically—a fundamental operation with applications in navigation, network analysis, web crawling, and game AI.

The key difference between BFS and DFS lies in their exploration strategy:

- **BFS**: Explores neighbors level by level (uses a queue)
- **DFS**: Explores as deeply as possible first (uses a stack or recursion)

# Breadth-First Search

BFS visits all vertices at distance $k$ before moving to distance $k+1$.

**Algorithm**:
```
BFS(G, start):
    queue = [start]
    visited = {start}

    while queue not empty:
        current = queue.dequeue()
        for each neighbor of current:
            if neighbor not visited:
                visited.add(neighbor)
                queue.enqueue(neighbor)
```

**Properties**:
- Time complexity: $O(n + m)$ where $n = |V|$, $m = |E|$
- Space complexity: $O(n)$
- **Finds shortest paths** in unweighted graphs
- Explores in a "wavefront" pattern

**Applications**: Shortest path finding, level-order tree traversal, social network distance analysis.

# Depth-First Search

DFS explores as far as possible along each branch before backtracking.

**Algorithm (Recursive)**:
```
DFS(G, start):
    visited = set()

    def dfs_recursive(current):
        visited.add(current)
        for each neighbor of current:
            if neighbor not visited:
                dfs_recursive(neighbor)

    dfs_recursive(start)
```

**Properties**:
- Time complexity: $O(n + m)$
- Space complexity: $O(n)$ (recursion stack depth)
- Does **not** guarantee shortest paths
- Explores in a "deep-then-backtrack" pattern

**Applications**: Cycle detection, topological sorting, maze solving, backtracking problems.

# Comparison

| Aspect | BFS | DFS |
|--------|-----|-----|
| **Data Structure** | Queue (FIFO) | Stack/Recursion (LIFO) |
| **Exploration** | Level-by-level | Depth-first |
| **Shortest Path** | Yes (unweighted) | No |
| **Use When** | Target nearby, need shortest path | Complete exploration, cycle detection |
| **Memory** | More for wide graphs | More for deep graphs |

# Interactive Visualization

The embedded video demonstrates BFS and DFS traversal algorithms in action.

<div style="text-align: center; margin: 2em 0;">
<iframe width="700" height="400" src="https://www.youtube.com/embed/HZ5YTanv5QE" title="BFS and DFS Visualization" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</div>

# Example

Consider graph with edges: (1,2), (1,3), (2,4), (2,5), (3,4), (4,6)

**BFS from vertex 1**: Visit order 1 → 2, 3 → 4, 5 → 6 (level-by-level)

**DFS from vertex 1**: Visit order 1 → 2 → 4 → 3 → 6 → 5 (depth-first)

The choice depends on problem requirements: BFS for shortest paths, DFS for complete exploration or topological sorting.

# Conclusion

BFS and DFS are foundational graph algorithms with $O(n + m)$ complexity but distinct exploration strategies. BFS finds shortest paths through level-by-level exploration, while DFS's depth-first approach suits topological sorting and cycle detection. Mastering both provides essential tools for graph-based problem solving.

# References

1. Cormen, T. H., et al. (2009). *Introduction to Algorithms* (3rd ed.). MIT Press.
2. Sedgewick, R., & Wayne, K. (2011). *Algorithms* (4th ed.). Addison-Wesley.

---

*Example paper made with Markdown + Pandoc for Scroll Press.*
