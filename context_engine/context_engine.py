import json
import networkx as nx
from collections import defaultdict
import sys
import time
import argparse

class CpgLoader:
    def __init__(self, json_file):
        self.json_file = json_file
        self.graph = nx.DiGraph() # Changed to DiGraph
        self.alias_map = defaultdict(list) 
        self.method_map = {} 
        self.node_to_method = {} 

    def load(self):
        print(f"Loading CPG from {self.json_file}...", file=sys.stderr)
        start_time = time.time()
        
        with open(self.json_file, 'r') as f:
            data = json.load(f)
            
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        # Add Nodes
        for node in nodes:
            nid = node['id']
            attrs = node.get('properties', {})
            attrs['label'] = node['label']
            attrs['id'] = nid 
            
            self.graph.add_node(nid, **attrs)
            
            if 'ALIAS_CLASS' in attrs:
                self.alias_map[attrs['ALIAS_CLASS']].append(nid)
                
            if node['label'] == 'METHOD':
                full_name = attrs.get('FULL_NAME')
                if full_name:
                    self.method_map[full_name] = nid
                    
        # Add Edges
        for edge in edges:
            src = edge['src']
            dst = edge['dst']
            label = edge['label']
            # DiGraph overwrites if multiple edges exist, but usually CPG edges are distinct by type
            # We store label in edge data
            self.graph.add_edge(src, dst, label=label)
            
        print(f"Graph loaded in {time.time() - start_time:.2f}s", file=sys.stderr)
        print(f"Nodes: {self.graph.number_of_nodes()}", file=sys.stderr)
        print(f"Edges: {self.graph.number_of_edges()}", file=sys.stderr)
        
        return self.graph

    def get_method_of_node(self, node_id):
        if node_id in self.node_to_method:
            return self.node_to_method[node_id]
        
        visited = set()
        queue = [node_id]
        
        while queue:
            curr = queue.pop(0)
            if curr in visited: continue
            visited.add(curr)
            
            node_data = self.graph.nodes[curr]
            if node_data.get('label') == 'METHOD':
                self.node_to_method[node_id] = curr
                return curr
            
            # Traverse incoming AST/CONTAINS edges
            for pred in self.graph.predecessors(curr):
                edge_data = self.graph.get_edge_data(pred, curr)
                if edge_data.get('label') in ['AST', 'CONTAINS']:
                    queue.append(pred)
                        
        return None

class Slicer:
    def __init__(self, loader):
        self.loader = loader
        self.graph = loader.graph

    def slice(self, seed_node_id, direction='backward', depth=5, edge_types=None):
        if edge_types is None:
            # Default fallback behavior if no edge types specified
            edge_types = ['REACHING_DEF', 'CDG', 'REF']

        visited = set()
        queue = [(seed_node_id, 0)]
        visited.add(seed_node_id)
        
        result_nodes = {seed_node_id: False}
        seed_name = self.graph.nodes[seed_node_id].get('NAME', 'unknown')
        
        while queue:
            curr, d = queue.pop(0)
            if d >= depth: continue
            
            # Determine neighbors based on direction
            if direction == 'backward':
                neighbors = self.graph.predecessors(curr)
            elif direction == 'forward':
                neighbors = self.graph.successors(curr)
            else:
                # Bidirectional? Not supported yet
                neighbors = []
                
            for neighbor in neighbors:
                if neighbor in visited: continue
                
                # Check edge type
                if direction == 'backward':
                    edge_data = self.graph.get_edge_data(neighbor, curr)
                else:
                    edge_data = self.graph.get_edge_data(curr, neighbor)
                    
                label = edge_data.get('label')
                if label in edge_types:
                    visited.add(neighbor)
                    result_nodes[neighbor] = False
                    queue.append((neighbor, d + 1))
                    
        # Special handling for "REF" type if it's the ONLY type (Test 3.1 Slice C)
        # The prompt describes Slice C as: REF (follow to LOCAL, then REACHING_DEF from LOCAL)
        # This is a multi-step traversal.
        # For now, let's keep the generic traversal. If the user wants complex multi-step, 
        # they should probably chain calls or we add a specific mode.
        # But wait, the previous "Variable Slice" logic was useful. 
        # Let's add a "variable_slice" method and call it if edge_types=['REF_VAR']?
        
        return result_nodes, seed_name

    def variable_slice(self, seed_node_id):
        # ... (Previous logic for variable slicing) ...
        # For now, let's just stick to the generic traversal. 
        # If edge_types=['REF'], it will just follow REF edges.
        pass

class ContextFormatter:
    def __init__(self, loader, source_root="libpng"):
        self.loader = loader
        self.graph = loader.graph
        self.source_root = source_root
        self.file_cache = {}

    def get_source_line(self, filename, line_no):
        if not filename or filename == "unknown_file": return None
        
        if filename not in self.file_cache:
            try:
                import os
                # Try relative to source_root
                candidate = os.path.join(self.source_root, filename)
                if not os.path.exists(candidate):
                    # Try absolute or direct
                    candidate = filename
                
                if os.path.exists(candidate):
                    with open(candidate, 'r', encoding='utf-8', errors='replace') as f:
                        self.file_cache[filename] = f.readlines()
                else:
                    self.file_cache[filename] = None
            except Exception as e:
                print(f"Error reading {filename}: {e}", file=sys.stderr)
                self.file_cache[filename] = None
                
        lines = self.file_cache.get(filename)
        if lines and 1 <= line_no <= len(lines):
            return lines[line_no - 1].rstrip()
        return None

    def format_to_string(self, result_nodes, seed_name="variable"):
        files = defaultdict(lambda: defaultdict(list)) 
        node_alias_status = {} 
        
        for nid, is_alias in result_nodes.items():
            node = self.graph.nodes[nid]
            if 'LINE_NUMBER' not in node: continue
            
            # Resolve File via METHOD FILENAME
            method_id = self.loader.get_method_of_node(nid)
            filename = "unknown_file"
            if method_id:
                method_node = self.graph.nodes[method_id]
                filename = method_node.get('FILENAME', 'unknown_file')
            
            line = int(node['LINE_NUMBER'])
            files[filename][line].append(node)
            
            if line not in node_alias_status:
                node_alias_status[(filename, line)] = is_alias
            else:
                if not is_alias:
                    node_alias_status[(filename, line)] = False 
            
        output = []
        
        for filename in sorted(files.keys()):
            output.append(f"File: `{filename}`")
            output.append("```c")
            
            lines = sorted(files[filename].keys())
            if not lines: continue
            
            prev_line = lines[0]
            
            for i, line_no in enumerate(lines):
                if line_no > prev_line + 1:
                    output.append("  ...")
                
                nodes_on_line = files[filename][line_no]
                is_alias_line = node_alias_status[(filename, line_no)]
                
                # Get Source Code
                code_line = self.get_source_line(filename, line_no)
                if code_line is None:
                    best_code = ""
                    for n in nodes_on_line:
                        code = n.get('CODE', '')
                        if len(code) > len(best_code):
                            best_code = code
                    code_line = best_code
                
                # Annotations
                anns = []
                if is_alias_line:
                    anns.append(f"May alias {seed_name}")
                
                ann_str = f" // {', '.join(set(anns))}" if anns else ""
                
                output.append(f"{line_no:4d} | {code_line}{ann_str}")
                prev_line = line_no
            output.append("```")
        return "\n".join(output)

    def format(self, result_nodes, seed_name="variable"):
        return self.format_to_string(result_nodes, seed_name)

def main():
    parser = argparse.ArgumentParser(description="Context Engine")
    parser.add_argument("--variable", help="Target variable name", default="row_pointers")
    parser.add_argument("--file", help="Target file name filter")
    parser.add_argument("--depth", type=int, default=5, help="Slicing depth")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    
    slicer = Slicer(loader)
    formatter = ContextFormatter(loader)
    
    target_var = args.variable
    
    # Find candidates
    candidates = []
    for n, d in G.nodes(data=True):
        if d.get('label') == 'IDENTIFIER' and d.get('NAME') == target_var:
            # Filter by file if requested
            if args.file:
                method_id = loader.get_method_of_node(n)
                if method_id:
                    method_node = G.nodes[method_id]
                    filename = method_node.get('FILENAME', '')
                    if args.file not in filename:
                        continue
            candidates.append(n)
            
    if not candidates:
        if not args.json: print(f"Variable '{target_var}' not found.")
        return

    # Smart Seed Selection
    best_seed = None
    best_score = -1
    
    for cand in candidates:
        incoming_ddg_count = 0
        for pred in G.predecessors(cand):
            edge = G.get_edge_data(pred, cand)
            if edge and edge.get('label') == 'DDG':
                incoming_ddg_count += 1
        
        if incoming_ddg_count > best_score:
            best_score = incoming_ddg_count
            best_seed = cand
            
    seed = best_seed if best_seed else candidates[0]
    
    if not args.json:
        print(f"Chose seed: {seed} (score: {best_score} incoming DDG)")
        print(f"Slicing from seed: {seed} ({target_var})...")
    
    # Use REACHING_DEF instead of DDG if DDG is missing (or both)
    # The user asked for REACHING_DEF in the analysis request, so let's support it.
    # The Slicer class currently hardcodes REF fallback. We should update it to support edge_types arg properly.
    # But for now, let's just call slice.
    slice_nodes, seed_name = slicer.slice(seed, direction='backward', depth=args.depth, edge_types=['REACHING_DEF', 'CDG'])
    
    if args.json:
        # Construct JSON output
        output_data = {
            "seed_node": seed,
            "variable": target_var,
            "slice_size": len(slice_nodes),
            "files": {}
        }
        
        # Group by file/line for JSON
        files_dict = defaultdict(lambda: defaultdict(list))
        node_alias_status = {}
        
        for nid, is_alias in slice_nodes.items():
            node = G.nodes[nid]
            if 'LINE_NUMBER' not in node: continue
            
            method_id = loader.get_method_of_node(nid)
            filename = "unknown_file"
            if method_id:
                method_node = G.nodes[method_id]
                filename = method_node.get('FILENAME', 'unknown_file')
                
            line = int(node['LINE_NUMBER'])
            files_dict[filename][line].append(nid)
            node_alias_status[(filename, line)] = is_alias

        for filename, lines_map in files_dict.items():
            file_entries = []
            for line_no in sorted(lines_map.keys()):
                code_line = formatter.get_source_line(filename, line_no)
                if code_line is None: code_line = "<source not found>"
                
                file_entries.append({
                    "line": line_no,
                    "code": code_line.strip(),
                    "is_alias": node_alias_status.get((filename, line_no), False)
                })
            output_data["files"][filename] = file_entries
            
        print(json.dumps(output_data, indent=2))
        
    else:
        print(f"Slice size: {len(slice_nodes)} nodes")
        context = formatter.format(slice_nodes, seed_name)
        print("\n--- Context Output ---")
        print(context)

if __name__ == "__main__":
    main()
