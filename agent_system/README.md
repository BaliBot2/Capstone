# 2-Agent CPG Analysis System

This directory contains the implementation of the dual-agent architecture for querying the CPG.

## Architecture
-   **Agent 1 (Scout)**: Navigates the graph using `igraph` and specialized tools.
-   **Agent 2 (Lead)**: Orchestrates the search and communicates with the user.

## Files
-   `cpg_interface.py`: The backend service that loads the CPG into memory and provides the "Fat Tools".
-   `agent_tools.py`: Tool definitions for the LLM agents.
-   `two_agent_system.py`: The main loop running the interaction between Lead and Scout.
