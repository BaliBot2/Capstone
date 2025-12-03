# Edge Type Contribution Analysis Report

## Executive Summary
This report validates which edge types produce the highest quality slices for the Context Engine. We analyzed single edge types and combinations on 10 test variables in `libpng`.

**Key Recommendations:**
1.  **Optimal Combination**: **`REACHING_DEF + CDG + REF`** (Combination C).
    *   **Reasoning**: `REACHING_DEF` provides the core data flow. `CDG` adds critical control dependencies (e.g., "why is this variable being updated?"). `REF` anchors the slice to the variable declaration.
2.  **Performance**: The optimal combination is fast (avg < 0.5ms per slice), making it suitable for real-time queries.
3.  **Noise Control**: `CFG` and `AST` edges add significant node count (noise) without proportional value for data flow understanding. They should be excluded from the default slice.

## Test 3.1: Single Edge Type Performance
We sliced 10 variables using only one edge type at a time.

| Variable | REACHING_DEF | CDG | REF | CFG | AST |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `row_pointers` | 23 | 74 | 1 | 2 | 2 |
| `png_ptr` | 60 | 28 | 1 | 1 | 1 |
| `i` | 2 | 7 | 1 | 7 | 6 |
| `buf` | 154 | 1 | 1 | 1 | 1 |

**Observations**:
*   **REACHING_DEF**: The workhorse. Captures the majority of relevant data flow nodes.
*   **CDG**: Essential for control flow variables (e.g., loop counters like `i`, conditional flags).
*   **REF**: Only finds the `LOCAL` declaration. Essential for context but not for traversal.
*   **CFG/AST**: Poor standalone performance for slicing.

## Test 3.2: Edge Type Combinations
We tested 5 combinations to find the best balance of context and noise.

| Combo | Description | Avg Nodes | Avg Time | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **A** | `REACHING_DEF` | 67 | 0.27ms | **Incomplete** (Misses control logic) |
| **B** | `REACHING_DEF + CDG` | 113 | 0.34ms | **Good** (Data + Control) |
| **C** | `REACHING_DEF + CDG + REF` | 115 | 0.30ms | **Best** (Anchored Data + Control) |
| **D** | `REACHING_DEF + REF` | 69 | 0.17ms | **Incomplete** |
| **E** | All Types | 184 | 0.40ms | **Noisy** (Too many CFG/AST nodes) |

**Analysis**:
*   Adding `CDG` (Combo B vs A) significantly improves the slice for complex logic (e.g., `row_pointers` nodes jump from 24 to 98).
*   Adding `REF` (Combo C vs B) adds minimal overhead but ensures the variable definition is included.
*   Combo E (All) bloats the slice with structural nodes that consume tokens without adding semantic value.

## Test 3.3: Edge Direction Validation
We verified that backward and forward slicing produce distinct, semantically correct results.

*   **Backward**: Traverses `predecessors` (History/Origins).
*   **Forward**: Traverses `successors` (Future/Impact).
*   **Result**: Confirmed distinct node sets for all tested variables.

## Conclusion
The Context Engine should be configured to use `['REACHING_DEF', 'CDG', 'REF']` as the default edge types for slicing. This configuration maximizes semantic relevance while minimizing token usage and latency.
