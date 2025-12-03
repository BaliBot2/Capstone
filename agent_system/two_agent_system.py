import os
import json
import datetime
import time
import google.generativeai as genai
from cpg_interface import CPGService
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="../.env")
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

genai.configure(api_key=api_key)

# Initialize CPG Service (Singleton-ish)
print("Initializing CPG Service...")
cpg_service = CPGService("../libpng_cpg_annotated.json")

# --- Logging Setup ---
class DualLogger:
    def __init__(self, filename="agent_session.log"):
        self.filename = filename
        # Clear previous log
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write(f"--- Agent Session Started: {datetime.datetime.now()} ---\n\n")
    
    def log(self, message):
        print(message)
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(str(message) + "\n")

logger = DualLogger()

# --- Tool Definitions for Scout ---

def search_codebase_tool(query: str):
    """Finds nodes matching the query."""
    return cpg_service.search_codebase(query)

def read_function_code_tool(function_name: str):
    """Reads the code of a function."""
    return cpg_service.read_function_code(function_name)

def get_file_structure_tool(filename: str):
    """Lists functions in a file."""
    return cpg_service.get_file_structure(filename)

def get_file_skeleton_tool(filename_query: str):
    """Generates a 'Virtual Header' for a file (signatures/types) without full code."""
    return cpg_service.get_file_skeleton(filename_query)

def trace_data_flow_tool(start_node_id: str, direction: str = "OUT", max_depth: int = 5):
    """Traces data flow from a node."""
    return cpg_service.trace_data_flow(start_node_id, direction, max_depth)

def trace_control_flow_tool(start_node_id: str, direction: str = "OUT", max_depth: int = 5):
    """Traces control flow (calls) from a node."""
    return cpg_service.trace_control_flow(start_node_id, direction, max_depth)

def summarize_neighborhood_tool(node_id: str, radius: int = 1):
    """Summarizes the local graph neighborhood."""
    return cpg_service.summarize_neighborhood(node_id, int(radius))

def analyze_structural_patterns_tool(file_node_id: str):
    """Scans for C design idioms (Opaque Pointers, VTables) to infer intent."""
    return cpg_service.analyze_structural_patterns(file_node_id)

def extract_business_rules_tool(variable_name: str, context_function: str):
    """Extracts 'Business Logic' by finding constraints (IF checks) on a variable."""
    return cpg_service.extract_business_rules(variable_name, context_function)

def analyze_architecture_layers_tool(file_query: str):
    """Determines if a file is 'Low Level' (Driver) or 'High Level' (Logic)."""
    return cpg_service.analyze_architecture_layers(file_query)

def identify_design_patterns_tool(function_name: str):
    """Scans for C idioms like Function Pointers, Void* Context, Singleton."""
    return cpg_service.identify_design_patterns(function_name)

def map_feature_cluster_tool(feature_seed_name: str):
    """Maps a 'Feature' to code by following Data Clusters."""
    return cpg_service.map_feature_cluster(feature_seed_name)

scout_tools = [
    search_codebase_tool,
    read_function_code_tool,
    get_file_structure_tool,
    get_file_skeleton_tool,
    trace_data_flow_tool,
    trace_control_flow_tool,
    summarize_neighborhood_tool,
    analyze_structural_patterns_tool,
    extract_business_rules_tool,
    analyze_architecture_layers_tool,
    identify_design_patterns_tool,
    map_feature_cluster_tool
]

def rephrase_query(user_input):
    """
    Refines a vague user symptom into a precise technical directive 
    for the Static Analysis Agents.
    """
    print(f"\n[System]: Analyzing intent for: '{user_input}'...")
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are a Technical Lead. Classify the user query into one of 5 MODES and generate a technical directive.
    
    1. MODE: DEBUG (Crash, error, bug) -> Inspect [Function] for [Error].
    2. MODE: EXPLAIN (Purpose, summary) -> Summarize [File].
    
    3. MODE: LOGIC (Rules, constraints, invariants)
       - Keywords: "What are the rules for...", "Can X be null?", "Constraints on..."
       - Directive: Extract Business Rules for [Variable] in [Function]. Identify invariants.
       
    4. MODE: ARCHITECTURE (Layers, structure, coupling)
       - Keywords: "High level view", "Architecture", "Dependencies"
       - Directive: Analyze Architecture Layers for [Module]. Check Fan-In/Fan-Out.
       
    5. MODE: DESIGN (Patterns, why this way)
       - Keywords: "Design pattern", "Why pointer?", "Strategy"
       - Directive: Identify Design Patterns in [Function]. Check for Polymorphism (Function Pointers) or Encapsulation.

    User: "{user_input}"
    Output:
    """
    
    try:
        response = model.generate_content(prompt)
        technical_query = response.text.strip()
        print(f"[System]: Technical Directive -> \"{technical_query}\"")
        return technical_query
    except Exception as e:
        print(f"[System]: Rephrasing failed ({e}). Using original query.")
        return user_input

# --- Agent Definitions ---

class ScoutAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            tools=scout_tools,
            system_instruction="""
            Role: Data Retrieval Unit.
            RULES:
            1. NO conversational filler.
            2. Call tools immediately.
            3. Retry on failure.
            4. Output: SUMMARY of findings.
            
            STRATEGY:
            - "How is X set?" -> `search_codebase("X =")`.
            - Design/Arch -> `analyze_structural_patterns`.
            """
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, prompt):
        # We append a directive to every prompt to enforce brevity
        full_prompt = f"{prompt} \n(FACTUAL DATA ONLY. NO FILLER.)"
        response = self.chat.send_message(full_prompt)
        logger.log(f"    [Scout Token Usage]: {response.usage_metadata}")
        return response.text

class LeadAgent:
    def __init__(self, scout):
        self.scout = scout
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            # NO tools passed here. We handle logic manually via JSON.
            generation_config={"response_mime_type": "application/json"},
            system_instruction="""
            Role: "Comprehension Engine" Code Architect.
            Constraint: 3 MOVES max.
            
            PROTOCOL FOR 'MODE: LOGIC':
            1. Goal: Extract Business Rules (Invariants).
            2. Behavior: Ask Scout to `extract_business_rules` for key variables.
            3. Final Output: A list of "Must be True" conditions (e.g., "Width must be > 0").
            
            PROTOCOL FOR 'MODE: DESIGN':
            1. Goal: Infer Architect Intent.
            2. Behavior: Ask Scout to `identify_design_patterns` and `map_feature_cluster`.
            3. Final Output: Explain the "Why" (e.g., "Used function pointers to decouple IO logic").
            
            PROTOCOL FOR 'MODE: DEBUG':
            1. Goal: Find Bugs.
            2. Behavior: Trace Data Flow + Error Handling.
            3. Final Output: The Bug + Fix.

            GENERAL RULES:
            - BATCH: Check Function + Error Handling + Data Flow in one go.
            - GUESS: Declare bug or pattern early.
            - DEPTH: Max 1 level deep.
            - VERBOSE: The Final Answer must be detailed and explain the reasoning.
            
            JSON OUTPUT:
            { "thought": "...", "command": "ASK_SCOUT"|"FINISH", "payload": "..." }
            """
        )
        self.chat = self.model.start_chat()

    def run_loop(self, user_query, max_turns=4): # HARD CAP at 4 (User requested 4)
        logger.log(f"\n--- Investigating (Rapid Mode): '{user_query}' ---\n")
        
        # Initial Kickoff
        response = self.chat.send_message(f"QUERY: {user_query}")
        
        for turn in range(max_turns):
            try:
                # 1. Parse JSON Response
                text_response = response.text
                logger.log(f"[Raw Lead Output]: {text_response}")
                data = json.loads(text_response)
                
                if isinstance(data, list):
                    if len(data) > 0: data = data[0]
                    else: raise ValueError("Received empty JSON list")
                
                command = data.get("command")
                payload = data.get("payload")
                thought = data.get("thought")
                
                logger.log(f"[Lead Turn {turn+1}/{max_turns}]: {thought}")

                # 2. Check for Victory
                if command == "FINISH":
                    return payload
                
                # 3. Forced Landing (The Logic Trap)
                # If we are at the last turn and the agent tries to keep searching, STOP IT.
                if turn == max_turns - 1:
                    logger.log("  [System]: Final turn reached. Forcing answer synthesis.")
                    # We don't execute the scout. We force the Lead to answer NOW.
                    final_prompt = (
                        "SYSTEM OVERRIDE: Investigation time is up. "
                        "Based on the code and traces you have seen so far, "
                        "provide the best possible explanation for the failure. "
                        "Do not ask for more data. Output JSON with command 'FINISH'."
                    )
                    response = self.chat.send_message(final_prompt)
                    
                    # Parse the forced answer immediately
                    try:
                        text_response = response.text
                        logger.log(f"[Raw Lead Output (Forced)]: {text_response}")
                        final_data = json.loads(text_response)
                        if isinstance(final_data, list): final_data = final_data[0]
                        return final_data.get("payload")
                    except:
                        return response.text # Fallback if it panics and outputs text

                # 4. Standard Execution (If not final turn)
                if command == "ASK_SCOUT":
                    logger.log(f"  > Batch Dispatch: {payload}")
                    
                    # Rate Limit Sleep (Crucial for Free Tier)
                    time.sleep(10) 
                    
                    scout_result = self.scout.ask(payload)
                    clean_result = scout_result[:1500] # Reduced to 1500 to save tokens
                    logger.log(f"  < Scout Returned: {len(clean_result)} chars.")
                    
                    response = self.chat.send_message(
                        f"SCOUT_DATA: {clean_result}\n\nNEXT_JSON_MOVE:"
                    )

            except json.JSONDecodeError:
                logger.log("  [System]: Lead output invalid JSON. Retrying...")
                time.sleep(2)
                response = self.chat.send_message("ERROR: Output valid JSON only.")
                
        return "Investigation timed out."

if __name__ == "__main__":
    scout = ScoutAgent()
    lead = LeadAgent(scout)
    
    # 2. Get User Input
    raw_query = "Identify design patterns in png_create_read_struct"
    
    # 3. The "Shift Left" Optimization
    technical_query = rephrase_query(raw_query)
    
    # 4. Execute the Agent Loop with the SUPERIOR query
    final_answer = lead.run_loop(technical_query, max_turns=4)
    
    logger.log("\n--- Final Answer ---")
    logger.log(final_answer)
