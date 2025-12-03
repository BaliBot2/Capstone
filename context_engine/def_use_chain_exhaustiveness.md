# Method 1: Def-Use Chain Exhaustiveness

**Measures:** Coverage sufficiency for data flow

## Ground Truth Generation

For seed variable X at line L, compute transitive closure of all REACHING_DEF edges (depth=∞) to find complete def-use web.

Extract "ground truth set" GT = all nodes reachable via REACHING_DEF in unlimited traversal.

For your slice at depth=k with edge config E, compute retrieved set R.

## Metrics

*   **Recall@Depth_k** = |R ∩ GT| / |GT|
*   **Marginal Information Gain** = Recall@k - Recall@(k-1)
*   **Saturation Point** = minimum depth where marginal gain < 5%

## Pass Criterion

Recall ≥ 95% at selected depth, OR marginal gain < 2% (diminishing returns)

## Implementation Complexity: Low

*   Single BFS/DFS traversal to generate GT
*   Set intersection for recall calculation
*   Already have graph structure
