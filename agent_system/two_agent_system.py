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

scout_tools = [
    search_codebase_tool,
    read_function_code_tool,
    get_file_structure_tool,
    get_file_skeleton_tool,
    trace_data_flow_tool,
    trace_control_flow_tool,
    summarize_neighborhood_tool
]

def rephrase_query(user_input):
    """
    Refines a vague user symptom into a precise technical directive 
    for the Static Analysis Agents.
    """
    print(f"\n[System]: Rephrasing query: '{user_input}'...")
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are a Senior C Developer. 
    Translate the user's vague bug report into a PRECISE, GRAPH-NATIVE investigation plan.
    
    Use the following mapping logic:
    - "Crash/Segfault" -> Check for NULL pointers, Use-After-Free, or Buffer Overflow.
    - "Garbage Output" -> Trace data flow backwards from output to origin (Taint Analysis).
    - "Stuck/Slow" -> Check loop termination conditions and lock acquisitions.
    - "Memory Leak" -> Check malloc/free pairing in the relevant scope.

    Output a single, dense sentence containing:
    1. Likely Function Name (guess based on standard naming conventions if not given, e.g., 'read_row', 'parse_header').
    2. Specific variables to trace.
    3. Specific check to perform.

    Examples:
    User: "The image parser crashes on bad headers."
    Output: Inspect `png_read_header` and `png_read_info`. Trace `length` variables for buffer overflows. Check `png_ptr` for NULL before dereference.

    User: "Why is the output image all black?"
    Output: Trace the data flow of the pixel buffer in `png_combine_row`. Check for uninitialized memory or zeroed-out palette indices.

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
            You are a Data Retrieval Unit. NOT an assistant.
            
            RULES:
            1. Do NOT speak. Do NOT explain why you are searching.
            2. Call the tool immediately.
            3. If a tool fails, try a different query immediately.
            4. Your final text output should be a SUMMARY of the findings, not a narrative.
            
            Example Output:
            "FOUND: function png_read_row at node #123.
             DATA_FLOW: row_buf -> memcpy -> row_pointers.
             ALERT: pointer 'row_buf' aliases with global 'png_ptr'."
             
            SEARCH STRATEGY:
            - If asked "How is variable X set?", use `search_codebase` with the query "X =" or "X ->".
            - Do not restrict yourself to the current function.
            """
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, prompt):
        # We append a directive to every prompt to enforce brevity
        full_prompt = f"{prompt} \n(Provide FACTUAL DATA ONLY. No conversational filler.)"
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
            You are a "Rapid Response" Code Architect.
            
            CRITICAL CONSTRAINT: You have exactly 3 MOVES to solve the problem.
            
            PROTOCOL:
            1. BATCH REQUESTS: Do not ask for one thing. Ask the Scout to check the Function, its Error Handling, AND its Data Flow in a single instruction.
            2. GUESS EARLY: If you see a "likely" cause (e.g., a missing check), declare it as the answer. Do not verify every edge case.
            3. IGNORE DEEP DEPTH: Do not trace more than 1 level deep unless critical.
            
            JSON OUTPUT:
            {
                "thought": "Reasoning...",
                "command": "ASK_SCOUT" or "FINISH",
                "payload": "Compound instruction for Scout OR Final Answer"
            }
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
                    time.sleep(4) 
                    
                    scout_result = self.scout.ask(payload)
                    clean_result = scout_result[:3000] # Increased context slightly for batching
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
    raw_query = "can you explain the purpose of the file readpng2.c?"
    
    # 3. The "Shift Left" Optimization
    technical_query = rephrase_query(raw_query)
    
    # 4. Execute the Agent Loop with the SUPERIOR query
    final_answer = lead.run_loop(technical_query, max_turns=4)
    
    logger.log("\n--- Final Answer ---")
    logger.log(final_answer)
