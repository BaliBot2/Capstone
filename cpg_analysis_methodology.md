# CPG Analysis Methodology

This document outlines the methodology used to analyze the Code Property Graph (CPG) generated for the project. The analysis is divided into three main components: Slice Distribution, Edge Types, and Query Ambiguity.

## 1. Slice Distribution Analysis
**Script:** `analyze_slice_distribution.py`

This analysis aims to understand the size, complexity, and performance characteristics of program slices generated from the CPG.

### Selection Strategy
To ensure representative results, the analysis selects **20 random `IDENTIFIER` nodes** that satisfy the following criteria:
*   **Node Type:** `IDENTIFIER`
*   **Connectivity:** Must have at least one incoming `REACHING_DEF` edge. This ensures the node is a valid starting point for backward slicing (i.e., it is a variable usage with a known definition).

### Test 1.1: Depth vs. Size Curve
*   **Objective:** Measure how slice size grows as the slicing depth increases.
*   **Method:** For each of the 20 seed nodes, backward slices are generated at varying depths: **1, 2, 3, 5, 7, and 10**.
*   **Metrics Collected:**
    *   **Node Count:** Total number of nodes in the slice.
    *   **Line Count:** Number of unique `(filename, line_number)` tuples involved.
    *   **Execution Time:** Time taken to generate the slice (in milliseconds).
*   **Output:** Average growth trends for nodes, lines, and time across all depths.

### Test 1.2: Size Distribution Histogram
*   **Objective:** Categorize slices based on their size at a fixed depth to identify "typical" slice sizes.
*   **Method:** Uses the results from **Depth = 5**.
*   **Buckets:**
    *   **Tiny:** 1-10 nodes
    *   **Small:** 11-30 nodes
    *   **Medium:** 31-100 nodes
    *   **Large:** 101-500 nodes
    *   **Huge:** 501+ nodes
*   **Output:** Frequency distribution and statistical summary (Mean, Median, Max).

### Test 1.3: Outlier Investigation
*   **Objective:** Understand the characteristics of extreme cases.
*   **Method:** Identifies the **3 smallest** and **3 largest** slices from the Depth=5 dataset.
*   **Analysis:** Examines the seed node's context, including:
    *   Whether it belongs to a `<global>` method.
    *   Its in-degree (number of incoming edges).

---

## 2. Edge Type Analysis
**Script:** `analyze_edge_types.py`

This analysis investigates the impact of different CPG edge types on the slicing process, helping to determine the optimal configuration for context retrieval.

### Selection Strategy
*   **Target Variables:** A mix of **10 variables**, including common names (e.g., `i`, `x`, `len`) and project-specific names (e.g., `row_pointers`, `png_ptr`).
*   **Seed Selection:** For each variable, the node with the **highest in-degree** is selected to ensure a rich graph neighborhood for testing.

### Test 3.1: Single Edge Type Slicing
*   **Objective:** Isolate the contribution of individual edge types.
*   **Method:** Performs backward slicing (Depth=5) using only one edge type at a time.
*   **Edge Types Tested:** `REACHING_DEF`, `CDG`, `REF`, `CFG`, `AST`.
*   **Metrics:** Node count and execution time.

### Test 3.2: Edge Type Combination Test
*   **Objective:** Evaluate how combining edge types affects slice completeness and size.
*   **Method:** Performs backward slicing (Depth=5) with cumulative combinations:
    *   **A:** `REACHING_DEF` (Data Flow)
    *   **B:** `REACHING_DEF` + `CDG` (Data + Control Dependence)
    *   **C:** `REACHING_DEF` + `CDG` + `REF` (Data + Control + References)
    *   **D:** `REACHING_DEF` + `REF`
    *   **E:** All Types (`REACHING_DEF`, `CDG`, `REF`, `CFG`, `AST`)
*   **Output:** Comparative table of slice sizes for each combination.

### Test 3.3: Edge Direction Validation
*   **Objective:** Sanity check to ensure backward and forward slicing produce distinct results.
*   **Method:** Compares **Backward** (Predecessors) vs. **Forward** (Successors) slices at Depth=1 for 5 random seeds.
*   **Validation:** Verifies that the set of nodes returned is different for the two directions.

---

## 3. Query Ambiguity Analysis
**Script:** `analyze_query_ambiguity.py`

This analysis assesses the ambiguity of variable names within the codebase to define effective strategies for locating specific code elements.

### Test 2.1: Name Ambiguity Analysis
*   **Objective:** Quantify how often variable names are reused across methods and files.
*   **Method:** Analyzes a set of common and project-specific variable names.
*   **Metrics:**
    *   **Total:** Total occurrences of the name.
    *   **Unique Methods:** Number of distinct methods containing the name.
    *   **Unique Files:** Number of distinct files containing the name.
    *   **Max/Method:** Maximum number of times the name appears in a single method.
*   **Strategy Classification:** Suggests a lookup strategy based on ambiguity:
    *   **Unique:** Direct lookup.
    *   **List:** Present a short list to the user.
    *   **Name+Method:** Requires method context to disambiguate.
    *   **Name+Line:** Requires line number context.

### Test 2.2: Line Number Precision Analysis
*   **Objective:** Determine if a line number is sufficient to uniquely identify a variable.
*   **Method:** Samples **50 lines** that contain identifiers.
*   **Metrics:** Counts the number of distinct identifiers on each line.
*   **Output:** Histogram showing the frequency of lines with 1, 2-3, 4-5, or 6+ identifiers.

### Test 2.3: Query Specification Test
*   **Objective:** Evaluate the effectiveness of different query parameters.
*   **Method:** Simulates queries against the CPG using various combinations of criteria:
    *   Name only
    *   Name + Line
    *   Name + Method
    *   Line only
    *   Name + File
    *   Name + File + Line
*   **Result Classification:**
    *   **Exact:** 1 match.
    *   **Not Found:** 0 matches.
    *   **Disambiguate:** 2-10 matches.
    *   **Too Many:** >10 matches.
