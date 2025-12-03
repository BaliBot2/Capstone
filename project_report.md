# Project Report: End-to-End CPG Analysis System

## 1. Executive Summary
This project established a complete pipeline for **Static Analysis with LLMs**, transforming raw C/C++ source code into an enriched **Code Property Graph (CPG)** and querying it using a **2-Agent Architecture**. The system enables "Contextual Slicing" to debug complex issues (like memory corruption in `libpng`) without overwhelming the LLM context window.

**Pipeline Overview:**
`Source Code` -> **[CPG Generation]** -> `Raw CPG` -> **[Stensgaard Analysis]** -> `Enriched CPG` -> **[2-Agent System]** -> `Root Cause`

---

## 2. Phase 1: CPG Generation & Enrichment

### 2.1 CPG Generation (`cpggen`)
-   **Tool**: We used `cpggen` (based on Joern/Ocular) to parse the `libpng` codebase.
-   **Output**: A `cpg.json` file containing the Abstract Syntax Tree (AST), Control Flow Graph (CFG), and Program Dependence Graph (PDG).
-   **Scale**: The graph contains ~70,000 nodes and ~500,000 edges, capturing the full structural complexity of the library.

### 2.2 Stensgaard Points-To Analysis (`stensgaard.py`)
-   **Objective**: The raw CPG lacks explicit links between pointers and the memory they point to. We implemented **Steensgaard's Algorithm** to infer these relationships.
-   **Implementation**:
    -   Parsed the CPG to identify pointer assignments (`x = &y`, `p = q`).
    -   Used a **Union-Find** data structure to group pointers into equivalence classes.
    -   **Overlay**: Injected new `POINTS_TO` edges into the JSON, enriching the graph with memory aliasing information.
-   **Impact**: This allows the agents to answer questions like "Does `row_buf` alias with `png_ptr`?" by traversing a single edge, rather than deducing it from code.

---

## 3. Phase 2: The 2-Agent Architecture

### 3.1 The Agents
1.  **Lead Agent ("The Architect")**:
    -   **Role**: Project Manager & Synthesizer.
    -   **Protocol**: Strict JSON-only communication.
    -   **Logic**: Uses a "Symptom-to-Query Map" to translate user issues into technical directives.
    -   **Constraint**: Hard cap of 4 turns to prevent rabbit holes.

2.  **Scout Agent ("The Investigator")**:
    -   **Role**: Data Retrieval Unit.
    -   **Tools**:
        -   `get_file_skeleton`: Returns function signatures/types (Virtual Header).
        -   `trace_data_flow`: Multi-hop taint analysis (leveraging PDG + Points-To edges).
        -   `search_codebase`: "Writers Search" for variable assignments.
    -   **Constraint**: "Skeletons First" policy to minimize context load.

### 3.2 The Workflow ("Shift Left")
1.  **Query Rephraser**: A specialized prompt translates vague input (e.g., "Why crash?") into a technical plan (e.g., "Inspect `png_read_row`, check `row_buf` for NULL").
2.  **Investigation Loop**:
    -   Lead issues JSON command (`ASK_SCOUT`).
    -   Scout executes tool and returns truncated data.
    -   Lead analyzes data and plans next move.
3.  **Forced Landing**: If the answer isn't found by Turn 4, the system forces a synthesis step based on available evidence.

---

## 4. Implementation Details

### 4.1 CPG Interface (`cpg_interface.py`)
-   **Backend**: `igraph` for efficient graph storage and traversal.
-   **Multigraph Support**: Fixed traversal logic to handle multiple edge types (CFG, PDG, POINTS_TO) between nodes.
-   **Leiden Analysis**: Initially explored for community detection but removed to streamline the system.

### 4.2 Agent System (`two_agent_system.py`)
-   **Dual Logger**: Captures full interaction traces to `agent_session.log` and console.
-   **Rate Limit Handling**: Integrated sleeps and robust error handling for Gemini Free Tier.
-   **JSON Parsing**: Custom logic to handle list/object variations in LLM output.

---

## 5. Evolution & Decisions
-   **Enrichment First**: We realized raw CPGs are insufficient for pointer analysis, necessitating the Stensgaard overlay.
-   **From Chatty to Ruthless**: We moved from conversational agents to strict JSON/Data-Extractor personas to improve efficiency.
-   **From Raw Code to Skeletons**: We implemented `get_file_skeleton` to stop agents from reading entire files, forcing them to rely on graph structure.
-   **From Open-Ended to Budgeted**: We introduced a "Turn Budget" to ensure the system always converges to an answer.

## 6. Future Work
-   **Vector Search**: Integrate embeddings for semantic search over the graph.
-   **Interactive UI**: Build a frontend for the interaction loop.
-   **Batch Processing**: Run the system over a suite of known bugs to benchmark performance.
