---
title: "Graph Traversal Algorithms: BFS and DFS"
authors:
  - name: Dorothy Gale
    affiliation: Department of Computer Science, Emerald City Technical Institute
  - name: Huckleberry Finn
    affiliation: Department of Computer Science, Emerald City Technical Institute
date: "January 5, 2025"
---

## Abstract

Graph traversal algorithms systematically visit vertices in a graph. This paper examines the two fundamental approaches: Breadth-First Search—BFS—explores level-by-level, while Depth-First Search—DFS—explores as deep as possible before backtracking. Understanding their distinct characteristics is essential for selecting the appropriate algorithm for path-finding, connectivity analysis, and graph-based problem solving.

*Example paper made with MyST Markdown for Scroll Press.*

## Graph Fundamentals

A graph $G = (V, E)$ consists of vertices $V$ and edges $E$ connecting pairs of vertices. **Graph traversal** visits all vertices systematically—a fundamental operation with applications in navigation, network analysis, web crawling, and game AI.

:::{note}
**Key Insight:** The choice between BFS and DFS fundamentally determines the order in which vertices are discovered, which impacts algorithm behavior in path-finding, cycle detection, and connectivity analysis.
:::

The key difference between BFS and DFS lies in their exploration strategy:

- **BFS** — Explores neighbors level by level using a queue
- **DFS** — Explores as deeply as possible first using a stack or recursion

## Breadth-First Search

BFS visits all vertices at distance $k$ before moving to distance $k+1$. This level-by-level approach guarantees finding the shortest path in unweighted graphs.

### Algorithm

::::{tab-set}
:::{tab-item} Pseudocode
```
BFS(G, start):
    queue = [start]
    visited = {start}

    while queue not empty:
        current = queue.dequeue()
        process(current)

        for each neighbor of current:
            if neighbor not visited:
                visited.add(neighbor)
                queue.enqueue(neighbor)
```
:::

:::{tab-item} Python Implementation
```python
from collections import deque

def bfs(graph, start):
    """
    Breadth-First Search implementation.

    Args:
        graph: Dictionary mapping vertices to lists of neighbors
        start: Starting vertex

    Returns:
        List of vertices in BFS order
    """
    visited = set([start])
    queue = deque([start])
    order = []

    while queue:
        vertex = queue.popleft()
        order.append(vertex)

        for neighbor in graph[vertex]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order

# Example graph
graph = {
    'A': ['B', 'C'],
    'B': ['A', 'D', 'E'],
    'C': ['A', 'F'],
    'D': ['B'],
    'E': ['B', 'F'],
    'F': ['C', 'E']
}

result = bfs(graph, 'A')
print(f"BFS traversal order: {result}")
```
:::
::::

:::{margin}
**Queue Property:** FIFO — First-In-First-Out ensures level-by-level exploration.
:::

### Complexity Analysis

::::{dropdown} Time Complexity
:open:

**Time: $O(|V| + |E|)$**

Each vertex is visited once at $O(|V|)$, and each edge is examined once during neighbor iteration at $O(|E|)$. For dense graphs where $|E| \approx |V|^2$, this becomes $O(|V|^2)$.
::::

::::{dropdown} Space Complexity
:open:

**Space: $O(|V|)$**

The queue can contain up to $O(|V|)$ vertices in the worst case—when all vertices at the same level are enqueued. The visited set also requires $O(|V|)$ space.
::::

### Applications

:::{admonition} Shortest Path Finding
:class: tip

BFS finds the shortest path in **unweighted graphs** because it explores vertices in order of increasing distance from the source. Once a vertex is reached, we've found the shortest path to it.
:::

**Other key applications:**
- **Web crawling** — Discover pages level-by-level from a seed URL
- **Social network analysis** — Find degrees of separation between users
- **Network broadcasting** — Optimal message propagation in networks
- **Peer-to-peer networks** — Locate resources by distance

## Depth-First Search

DFS explores as deeply as possible along each branch before backtracking. This approach naturally uses a stack—either explicit or via recursion.

### Algorithm

::::{tab-set}
:::{tab-item} Pseudocode
```
DFS(G, start):
    stack = [start]
    visited = {start}

    while stack not empty:
        current = stack.pop()
        process(current)

        for each neighbor of current:
            if neighbor not visited:
                visited.add(neighbor)
                stack.push(neighbor)
```
:::

:::{tab-item} Python Iterative
```python
def dfs_iterative(graph, start):
    """
    Depth-First Search iterative implementation.

    Args:
        graph: Dictionary mapping vertices to lists of neighbors
        start: Starting vertex

    Returns:
        List of vertices in DFS order
    """
    visited = set([start])
    stack = [start]
    order = []

    while stack:
        vertex = stack.pop()
        order.append(vertex)

        # Add neighbors in reverse to maintain left-to-right exploration
        for neighbor in reversed(graph[vertex]):
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append(neighbor)

    return order

# Using same graph as BFS example
result = dfs_iterative(graph, 'A')
print(f"DFS traversal order: {result}")
```
:::

:::{tab-item} Python Recursive
```python
def dfs_recursive(graph, vertex, visited=None, order=None):
    """
    Depth-First Search recursive implementation.

    Args:
        graph: Dictionary mapping vertices to lists of neighbors
        vertex: Current vertex being visited
        visited: Set of already visited vertices
        order: List accumulating traversal order

    Returns:
        List of vertices in DFS order
    """
    if visited is None:
        visited = set()
        order = []

    visited.add(vertex)
    order.append(vertex)

    for neighbor in graph[vertex]:
        if neighbor not in visited:
            dfs_recursive(graph, neighbor, visited, order)

    return order

# Using same graph
result = dfs_recursive(graph, 'A')
print(f"DFS recursive traversal order: {result}")
```
:::
::::

:::{margin}
**Stack Property:** LIFO — Last-In-First-Out enables depth-first exploration.
:::

### Complexity Analysis

::::{dropdown} Time Complexity
:open:

**Time: $O(|V| + |E|)$**

Identical to BFS—each vertex and edge is processed once. The traversal order differs but asymptotic complexity is the same.
::::

::::{dropdown} Space Complexity
:open:

**Space: $O(|V|)$**

Worst case: $O(|V|)$ for the stack in iterative version, or $O(|V|)$ recursion depth in recursive version with stack frames. Best case: $O(h)$ where $h$ is the height of the DFS tree.
::::

### Applications

:::{admonition} Cycle Detection
:class: tip

DFS naturally detects cycles: if we encounter a vertex that's in our current recursion stack—not just previously visited—we've found a cycle. This is crucial for dependency analysis and deadlock detection.
:::

**Other key applications:**
- **Topological sorting** — Order tasks respecting dependencies (requires DAG)
- **Maze solving** — Explore paths until finding exit or dead end
- **Connected components** — Identify separate subgraphs in disconnected graphs
- **Strongly connected components** — Tarjan's and Kosaraju's algorithms use DFS

## Comparative Analysis

### When to Use BFS vs DFS

The table below summarizes the key decision factors:

| Criterion | BFS | DFS |
|-----------|-----|-----|
| **Shortest path** — unweighted | ✓ Optimal | ✗ Not guaranteed |
| **Memory efficiency** — deep graphs | ✗ High memory | ✓ Lower memory |
| **Completeness** — infinite graphs | ✓ Complete | ✗ May get stuck |
| **Cycle detection** | Possible | ✓ Natural |
| **Topological sorting** | Not applicable | ✓ Natural |
| **Path exists checking** | Either works | Either works |

:::{warning}
**Infinite Graphs:** DFS can get stuck exploring an infinite branch and never backtrack to find the goal. BFS will eventually find any reachable goal at finite depth.
:::

### Example: Social Network Analysis

Consider finding the connection between two users in a social network:

```python
def find_connection_bfs(graph, start, target):
    """Find shortest path between two users using BFS."""
    if start == target:
        return [start]

    visited = {start}
    queue = deque([(start, [start])])

    while queue:
        vertex, path = queue.popleft()

        for neighbor in graph[vertex]:
            if neighbor == target:
                return path + [neighbor]

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None  # No connection exists

# Example: Finding connection between users
social_network = {
    'Alice': ['Bob', 'Charlie'],
    'Bob': ['Alice', 'David', 'Eve'],
    'Charlie': ['Alice', 'Frank'],
    'David': ['Bob'],
    'Eve': ['Bob', 'Frank'],
    'Frank': ['Charlie', 'Eve']
}

path = find_connection_bfs(social_network, 'Alice', 'Frank')
if path:
    print(f"Connection found: {' → '.join(path)}")
    print(f"Degrees of separation: {len(path) - 1}")
```

:::{note}
BFS guarantees finding the shortest path—minimum degrees of separation—which is why LinkedIn and Facebook use BFS-based algorithms for "mutual connections" features.
:::

## Advanced Topics

### Bidirectional Search

For large graphs, **bidirectional BFS** can significantly improve performance by searching simultaneously from both start and target vertices until the frontiers meet.

**Time complexity improvement:** $O(b^{d/2} + b^{d/2}) = O(b^{d/2})$ compared to $O(b^d)$ for unidirectional BFS, where $b$ is the branching factor and $d$ is the distance.

### Weighted Graphs

For graphs with weighted edges, neither BFS nor DFS guarantees optimal paths. **Dijkstra's algorithm**—a weighted variant of BFS using a priority queue—or **A\* search** are required.

## Conclusion

BFS and DFS represent fundamental graph traversal strategies with complementary strengths. BFS excels at finding shortest paths and works well for shallow, wide graphs, while DFS is memory-efficient for deep graphs and naturally supports cycle detection and topological sorting. Understanding when to apply each algorithm is essential for effective algorithm design.

**Key takeaway:** The choice between BFS and DFS depends on problem requirements (shortest path vs memory efficiency), graph structure (wide vs deep), and desired properties (completeness, cycle detection).

## References

1. Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms*, 4th ed. MIT Press.
2. Sedgewick, R., & Wayne, K. (2011). *Algorithms*, 4th ed. Addison-Wesley.
3. Skiena, S. S. (2020). *The Algorithm Design Manual*, 3rd ed. Springer.

---

*Example paper made with MyST Markdown for Scroll Press.*
