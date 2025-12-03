import igraph as ig
import json

class CPGMermaidGenerator:
    def __init__(self, cpg_service):
        self.cpg_service = cpg_service
        self.g = cpg_service.g
        self.idx_to_id = cpg_service.idx_to_id
        self.idx_to_label = cpg_service.idx_to_label

    def generate_mermaid(self, function_name_or_id):
        """
        Generates a Mermaid flowchart for a given function.
        """
        # 1. Find the METHOD node
        if isinstance(function_name_or_id, str) and not function_name_or_id.isdigit():
            # Search by name
            candidates = self.cpg_service.search_codebase(function_name_or_id)
            if not candidates:
                return f"Error: Function '{function_name_or_id}' not found."
            # Pick the first METHOD node
            method_node = None
            for node in candidates:
                if node['label'] == 'METHOD':
                    method_node = node
                    break
            if not method_node:
                return f"Error: No METHOD node found for '{function_name_or_id}'."
            # The search_codebase returns dicts with 'id' which maps to the graph index if we trust idx_to_id logic
            # But wait, search_codebase in cpg_interface returns:
            # {"id": self.idx_to_id[v.index], "label": v["label"], ...}
            # So 'id' is the string ID. We need to map it back to index.
            
            # Let's check what search_codebase actually returns.
            # It returns a list of dicts.
            # We need to find the vertex in the graph that matches this ID.
            
            target_id = method_node['id']
            # In CPGService, idx_to_id maps index -> string ID.
            # We need string ID -> index.
            # We can build a reverse map or just iterate (slow).
            # Or better, let's assume CPGService exposes a way or we build it.
            
            # Optimization: Build id_to_idx map if not present
            if not hasattr(self, 'id_to_idx'):
                self.id_to_idx = {v: k for k, v in self.idx_to_id.items()}
                
            start_node_idx = self.id_to_idx.get(target_id)
            if start_node_idx is None:
                 return f"Error: Could not map ID '{target_id}' to graph index."
        else:
            # ID lookup
            start_node_idx = int(function_name_or_id)

        # 2. Traverse the AST/CFG to build the graph
        # We want to show the control flow within the function.
        # We'll use a BFS/DFS starting from the METHOD node, following AST or CFG edges.
        # For a flowchart, CFG is usually better, but AST gives structure (blocks).
        # Let's try to reconstruct a flow view.
        
        mermaid_lines = ["flowchart TD"]
        
        # We need to map CPG IDs to Mermaid IDs (safe strings)
        def safe_id(idx):
            return f"node_{idx}"

        # Get all nodes reachable via AST edges (to get the code structure)
        # Or better, just get all nodes belonging to this function.
        # In CPG, nodes usually have an edge from METHOD via AST/CONTAINS.
        
        # Let's collect all nodes in the function first.
        # A simple way is to trace AST edges downwards.
        
        visited = set()
        queue = [start_node_idx]
        function_nodes = set()
        
        while queue:
            u = queue.pop(0)
            if u in visited:
                continue
            visited.add(u)
            function_nodes.add(u)
            
            # Get children via AST
            # Note: CPGService might not expose raw igraph efficiently, let's use the graph directly
            # Edge type 'AST' or 'CFG'? AST defines ownership.
            
            # We need to filter edges by type. 
            # In igraph, g.es[edge_index]['label'] gives the type.
            
            neighbors = self.g.neighbors(u, mode="out")
            for v in neighbors:
                # Check edge type
                eids = self.g.get_eids([(u, v)])
                for eid in eids:
                    if self.g.es[eid]['label'] == 'AST':
                        queue.append(v)
        
        # Now we have all nodes in the function.
        # Let's generate edges for CFG (Control Flow) to show the flow.
        
        edges_to_draw = []
        
        for u in function_nodes:
            neighbors = self.g.neighbors(u, mode="out")
            for v in neighbors:
                if v in function_nodes:
                    # Check for CFG edges
                    eids = self.g.get_eids([(u, v)])
                    for eid in eids:
                        if self.g.es[eid]['label'] == 'CFG':
                            edges_to_draw.append((u, v))
                            
        # Generate Mermaid Nodes
        for u in function_nodes:
            # Access attributes via CPGService dictionaries
            label = self.cpg_service.idx_to_label.get(u, 'UNKNOWN')
            code = self.cpg_service.idx_to_code.get(u, '').replace('"', "'").replace('\n', ' ')
            name = self.cpg_service.idx_to_name.get(u, '')
            
            # Styling based on type
            shape_start = "["
            shape_end = "]"
            
            if label == 'METHOD':
                text = f"Method: {name}"
                shape_start = "(("
                shape_end = "))"
            elif label == 'CALL':
                text = f"Call: {name}\\n{code}"
            elif label == 'CONTROL_STRUCTURE':
                text = f"{code}"
                shape_start = "{"
                shape_end = "}"
            elif label == 'RETURN':
                text = f"Return: {code}"
                shape_start = "(("
                shape_end = "))"
            else:
                text = f"{label}: {code}"
                
            # Truncate long text
            if len(text) > 50:
                text = text[:47] + "..."
                
            mermaid_lines.append(f'    {safe_id(u)}{shape_start}"{text}"{shape_end}')

        # Generate Mermaid Edges
        for u, v in edges_to_draw:
            mermaid_lines.append(f"    {safe_id(u)} --> {safe_id(v)}")
            
        return "\n".join(mermaid_lines)

    def generate_d3_json(self, function_name_or_id):
        """
        Generates a D3-compatible JSON tree for a given function.
        Format: {"name": "root", "children": [...]}
        """
        # 1. Find the METHOD node (Reuse logic)
        if isinstance(function_name_or_id, str) and not function_name_or_id.isdigit():
            candidates = self.cpg_service.search_codebase(function_name_or_id)
            if not candidates: return {"error": f"Function '{function_name_or_id}' not found."}
            target_id = None
            for node in candidates:
                if node['label'] == 'METHOD':
                    target_id = node['id']
                    break
            if not target_id: return {"error": f"No METHOD node found for '{function_name_or_id}'."}
            
            # Map ID to index
            if not hasattr(self, 'id_to_idx'):
                self.id_to_idx = {v: k for k, v in self.idx_to_id.items()}
            start_node_idx = self.id_to_idx.get(target_id)
        else:
            start_node_idx = int(function_name_or_id)

        if start_node_idx is None: return {"error": "Invalid node ID"}

        # 2. Build Tree via AST edges
        # D3 usually expects a tree structure. AST is perfect for this.
        
        def build_tree(u):
            label = self.cpg_service.idx_to_label.get(u, 'UNKNOWN')
            name = self.cpg_service.idx_to_name.get(u, '')
            code = self.cpg_service.idx_to_code.get(u, '')
            
            node_dict = {
                "name": label,
                "value": name if name else code[:20],
                "children": []
            }
            
            # Get AST children
            neighbors = self.g.neighbors(u, mode="out")
            for v in neighbors:
                eids = self.g.get_eids([(u, v)])
                for eid in eids:
                    if self.g.es[eid]['label'] == 'AST':
                        child_node = build_tree(v)
                        node_dict["children"].append(child_node)
            
            if not node_dict["children"]:
                del node_dict["children"]
                
            return node_dict

        return build_tree(start_node_idx)

    def generate_codebase_uml(self):
        """
        Generates a Mermaid Class Diagram for the entire codebase.
        Files are treated as Classes.
        Functions are treated as Methods.
        """
        from collections import defaultdict
        
        files_to_methods = defaultdict(list)
        
        # 1. Group methods by file
        for i in range(self.g.vcount()):
            if self.cpg_service.idx_to_label.get(i) == 'METHOD':
                # Get filename
                fname = self.cpg_service.idx_to_file.get(i, 'UNKNOWN_FILE')
                if not fname or fname == 'N/A': continue
                
                # Sanitize filename for Mermaid class name
                # e.g. "libpng/png.c" -> "libpng_png_c"
                safe_fname = fname.replace('/', '_').replace('\\', '_').replace('.', '_').replace('-', '_')
                
                method_name = self.cpg_service.idx_to_name.get(i, 'anonymous')
                
                # Sanitize method name
                # Replace <global>, <clinit> with safe names
                safe_method_name = method_name.replace('<', '').replace('>', '').replace('~', 'destructor_')
                # Escape other special chars if needed, but usually () are fine in display text if quoted, 
                # but here they are part of the method name string in class diagram syntax: +method()
                # Mermaid expects: +method_name()
                # If method_name contains spaces or weird chars, it might break.
                safe_method_name = safe_method_name.replace(' ', '_').replace('-', '_')
                
                files_to_methods[safe_fname].append(safe_method_name)
                
        # 2. Generate Mermaid
        mermaid_lines = ["classDiagram"]
        
        for fname, methods in files_to_methods.items():
            mermaid_lines.append(f"    class {fname} {{")
            # Limit methods to avoid huge diagrams? 
            # Let's show all for now, or top 20.
            for m in methods[:20]: 
                mermaid_lines.append(f"        +{m}()")
            if len(methods) > 20:
                mermaid_lines.append(f"        +... ({len(methods)-20} more)")
            mermaid_lines.append("    }")
            
        return "\n".join(mermaid_lines)

if __name__ == "__main__":
    # Test stub
    from cpg_interface import CPGService
    print("Loading CPG...")
    service = CPGService("../libpng_cpg_annotated.json")
    generator = CPGMermaidGenerator(service)
    
    # print("Generating Mermaid for 'png_read_row'...")
    # mermaid_code = generator.generate_mermaid("png_read_row")
    # print("\n--- Mermaid Code ---\n")
    # print(mermaid_code[:500] + "...")
    
    # print("\nGenerating D3 JSON for 'png_read_row'...")
    # d3_json = generator.generate_d3_json("png_read_row")
    # print("\n--- D3 JSON ---\n")
    # print(json.dumps(d3_json, indent=2)[:500] + "...")

    print("\nGenerating Codebase UML...")
    uml = generator.generate_codebase_uml()
    print("\n--- Codebase UML ---\n")
    print(uml[:1000] + "...")
