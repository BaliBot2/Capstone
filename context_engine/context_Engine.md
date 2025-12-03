# Context Engine

## Purpose
The `context_engine.py` file serves as the core engine for interacting with and analyzing Code Property Graphs (CPGs). Its primary purpose is to enable **context-aware code navigation and analysis** by performing program slicing. It allows users (and other scripts) to start from a specific variable or node in the code and traverse the graph to find relevant dependencies, definitions, and usages, effectively isolating the "context" of that element.

## Operational Context
The Context Engine operates within a larger CPG analysis framework. It acts as the central library that provides graph loading, traversal, and formatting capabilities to other specialized analysis scripts.

### Key Components
The engine is structured around three main classes:

1.  **`CpgLoader`**
    *   **Role:** Responsible for ingesting the CPG data (typically from a JSON file like `libpng_cpg_ddg.json`).
    *   **Functionality:** It constructs a directed graph (using `networkx`) where nodes represent code elements (identifiers, methods, etc.) and edges represent relationships (AST, CFG, DDG/REACHING_DEF, CDG). It also maintains indices for quick lookups, such as mapping nodes to their containing methods.

2.  **`Slicer`**
    *   **Role:** The core logic for traversing the graph.
    *   **Functionality:** It implements program slicing algorithms. Given a "seed" node (e.g., a variable usage), it traverses the graph in a specified direction (backward or forward) up to a certain depth. It filters traversal based on edge types (e.g., following `REACHING_DEF` for data flow or `CDG` for control dependence), effectively gathering the subset of the graph that affects or is affected by the seed.

3.  **`ContextFormatter`**
    *   **Role:** Bridges the gap between graph nodes and human-readable source code.
    *   **Functionality:** It takes the set of nodes resulting from a slice and maps them back to their original source files and line numbers. It retrieves the actual source code lines and formats them into a readable report (often in Markdown), grouping lines by file and annotating them with relevant information (e.g., "May alias variable X").

### Usage Scenarios
*   **Standalone CLI:** It can be executed directly from the command line to generate a context report for a specific variable (e.g., `python context_engine.py --variable row_pointers`).
*   **Library for Analysis:** It is imported by other scripts to perform bulk analysis:
    *   `analyze_slice_distribution.py`: Uses `CpgLoader` and `Slicer` to study the size and properties of slices.
    *   `analyze_edge_types.py`: Uses `Slicer` to test the impact of different edge types on slice quality.
    *   `analyze_query_ambiguity.py`: Uses `CpgLoader` to query the graph structure and assess variable name uniqueness.
