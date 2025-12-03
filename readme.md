# Bali-God: 2-Agent CPG Analysis System

**Bali-God** is an advanced static analysis tool that uses a **Code Property Graph (CPG)** and a **2-Agent LLM Architecture** to debug and analyze C/C++ codebases (specifically `libpng`).

## 🚀 Key Features

-   **2-Agent Architecture**:
    -   **Lead Agent**: A "Ruthless Architect" that plans investigations using strict JSON commands.
    -   **Scout Agent**: A "Data Extractor" that navigates the graph using structural tools.
-   **Graph-Native Tools**:
    -   `trace_data_flow`: Multi-hop taint analysis.
    -   `get_file_skeleton`: "Virtual Header" generation (no raw code reading).
    -   `search_codebase`: "Writers Search" for assignments.
-   **Optimized Workflow**:
    -   **Query Rephraser**: Translates vague symptoms into technical directives.
    -   **Forced Landing**: Guarantees an answer within 4 turns.
    -   **Dual Logging**: Full session traces in `agent_system/agent_session.log`.

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