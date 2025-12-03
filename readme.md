# Semantic Guided Agentic Navigation for Program Comprehension

**Aditya Bali**  
Ashoka University  
aditya.bali@ashoka.edu.in  

**Viom Kapur**  
Ashoka University  
viom.kapur@ashoka.edu.in  

**December 3, 2025**

## 1. Introduction
We propose **Semantic Guided Efficient Navigation**, a Hybrid Agentic Architecture that mimics a senior developer’s workflow by treating modules as "black boxes" and only inspecting specific logic when necessary. This solution constructs a **Code Property Graph (CPG)**—fusing Abstract Syntax Trees (AST), Control Flow Graphs (CFG), and Program Dependence Graphs (PDG) with Steensgaard’s pointer analysis—to serve as a structural foundation for a **2-Agent System**:
*   **Scout**: Navigates high-level "skeleton" abstractions to conserve context.
*   **Lead**: Executes precise graph traversals to fetch source code only when explicitly directed.

## 2. Background
Legacy software systems, particularly those architected in low-level languages like C and C++, constitute the immutable bedrock of critical global infrastructure. For modern maintainers, the primary bottleneck shifts from writing new code to comprehending this "cluttered mass" of existing logic. Standard "Chat with Code" LLM approaches fail due to:
*   **Context Explosion**: Repositories far exceed token limits (e.g., Linux Kernel is ~400M tokens).
*   **Structural Blindness**: LLMs treat code as flat text, hallucinating connections that violate rigid control flow and memory aliasing rules.

## 3. Methodology
### Static Code Analysis & CPG
We utilize a **Code Property Graph (CPG)** as the comprehensive unified representation, merging AST, CFG, and PDG.
*   **Base Generation**: Uses Joern to generate the initial CPG.
*   **Enrichment**: We implemented a custom **Steensgaard’s Points-To Analysis** (O(Nα(N))) to add explicit `POINTS_TO` edges, allowing agents to "see" through indirect memory accesses (pointer aliasing).

### Neuro-Cognitive Architecture
A **Dual-Agent Cognitive Loop** separates planning from perception:
1.  **The Router ("Shift Left")**: Intercepts user queries, classifies intent (DEBUG, EXPLAIN, LOGIC, ARCHITECTURE, DESIGN), and translates them into precise Technical Directives.
2.  **The Lead Agent (Planner)**: Formulates a Chain of Thought (CoT) and issues commands. It does not look at raw code directly.
3.  **The Scout Agent (Perception)**: Executes graph tools (`trace_data_flow`, `get_file_skeleton`, `search_codebase`) to retrieve factual topological data.

## 4. Results
The system was evaluated on the `libpng` codebase (70k+ nodes, 498k+ edges).
*   **Success Rate**: 100% on 7 test queries across LOGIC, DESIGN, and DEBUG modes.
*   **Efficiency**: Average response time of 59.0s.
*   **Accuracy**: 85.7% accuracy with 100% recall against ground truth criteria.
*   **Key Findings**: The system successfully identifies complex bugs (e.g., buffer overflows, memory leaks) and architectural patterns (e.g., Strategy Pattern) by tracing data flow across function boundaries, preventing hallucinations common in text-only RAG.

---

## 📂 Project Structure

```
bali-god/
├── agent_system/
│   ├── two_agent_system.py  # Main Entry Point (Agents, Loop, Rephraser)
│   ├── cpg_interface.py     # CPG Backend (igraph, Tools)
│   ├── agent_session.log    # Interaction Logs
│   └── README.md            # Agent Documentation
├── cpg_analysis/
│   └── ...                  # Analysis artifacts
├── libpng_cpg_annotated.json # The Code Property Graph
└── project_report.md        # Detailed Project Report
```

## 🛠️ Usage

1.  **Setup**:
    -   Ensure `GEMINI_API_KEY` is set in `.env`.
    -   Install dependencies: `igraph`, `google-generativeai`, `python-dotenv`.

2.  **Run the System**:
    ```bash
    cd agent_system
    python two_agent_system.py
    ```

3.  **Modify Query**:
    -   Edit the `raw_query` variable in `two_agent_system.py` to ask different questions (e.g., "Why is png_read_row failing?").

## 🧠 Design Philosophy

-   **Shift Left**: We fix the query *before* the agents start.
-   **Skeletons First**: We look at structure *before* reading code.
-   **Ruthless Efficiency**: We use JSON and turn budgets to prevent "rabbit holes".