import sys
import json
from collections import defaultdict, Counter
from context_engine import CpgLoader

def verify_cpg_audit():
    with open("cpg_audit_report.txt", "w", encoding="utf-8") as f:
        def log(msg):
            print(msg)
            f.write(msg + "\n")
            
        log("Loading CPG...")
        loader = CpgLoader("libpng_cpg_ddg.json")
        G = loader.load()
        
        log("\n=== Phase 1: The Inventory Audit (Nodes) ===")
        node_counts = Counter()
        method_with_name = 0
        total_methods = 0
        
        for n, d in G.nodes(data=True):
            label = d.get('label')
            node_counts[label] += 1
            
            if label == 'METHOD':
                total_methods += 1
                if d.get('NAME'):
                    method_with_name += 1
                    
        required_nodes = ['FILE', 'NAMESPACE_BLOCK', 'TYPE_DECL', 'METHOD', 'METHOD_PARAMETER_IN', 'METHOD_RETURN', 'CALL', 'IDENTIFIER', 'LITERAL', 'BLOCK', 'CONTROL_STRUCTURE']
        
        log(f"{'Node Type':<25} | {'Count':<8} | {'Status'}")
        log("-" * 45)
        for req in required_nodes:
            count = node_counts[req]
            status = "OK" if count > 0 else "MISSING"
            log(f"{req:<25} | {count:<8} | {status}")
            
        log(f"\nMethod Name Check: {method_with_name}/{total_methods} methods have NAME property.")
        if method_with_name == total_methods and total_methods > 0:
            log("Status: PASS")
        else:
            log("Status: FAIL (Some methods missing names)")

        log("\n=== Phase 2: The Connectivity Audit (Edges) ===")
        
        # 1. Syntax connectivity (AST)
        ast_edges = 0
        nodes_with_incoming_ast = set()
        total_nodes = G.number_of_nodes()
        
        # 2. Execution Order (CFG)
        cfg_edges = 0
        call_to_call_cfg = 0
        
        # 3. Data Dependencies (REACHING_DEF)
        rd_edges = 0
        identifiers_with_rd = set()
        total_identifiers = node_counts['IDENTIFIER']
        
        # 4. Interprocedural Link (CALL)
        call_edges = 0
        call_to_method_edges = 0
        
        for u, v, d in G.edges(data=True):
            label = d.get('label')
            
            if label == 'AST':
                ast_edges += 1
                nodes_with_incoming_ast.add(v)
                
            elif label == 'CFG':
                cfg_edges += 1
                u_label = G.nodes[u].get('label')
                v_label = G.nodes[v].get('label')
                if u_label == 'CALL' and v_label == 'CALL':
                    call_to_call_cfg += 1
                    
            elif label == 'REACHING_DEF':
                rd_edges += 1
                if G.nodes[v].get('label') == 'IDENTIFIER':
                    identifiers_with_rd.add(v)
                    
            elif label == 'CALL':
                call_edges += 1
                if G.nodes[v].get('label') == 'METHOD':
                    call_to_method_edges += 1

        log(f"AST Edges: {ast_edges}")
        ast_coverage = len(nodes_with_incoming_ast) / total_nodes if total_nodes > 0 else 0
        log(f"AST Node Coverage: {ast_coverage:.2%} (Expect high, but Root/Files have no incoming AST)")
        
        log(f"CFG Edges: {cfg_edges}")
        log(f"CALL -> CALL CFG Edges: {call_to_call_cfg}")
        log(f"Status: {'PASS' if call_to_call_cfg > 0 else 'FAIL'} (Execution Order)")
        
        log(f"REACHING_DEF Edges: {rd_edges}")
        rd_coverage = len(identifiers_with_rd) / total_identifiers if total_identifiers > 0 else 0
        log(f"Identifier RD Coverage: {rd_coverage:.2%}")
        log(f"Status: {'PASS' if rd_coverage > 0.5 else 'WARNING'} (Data Dependencies)")
        
        log(f"CALL Edges (Interprocedural): {call_edges}")
        log(f"CALL -> METHOD Edges: {call_to_method_edges}")
        log(f"Status: {'PASS' if call_to_method_edges > 0 else 'FAIL'} (Interprocedural Link)")

        log("\n=== Phase 3: The Gap Audit (Missing Links) ===")
        
        arg_to_param = 0
        ret_to_call = 0
        points_to = 0
        
        for u, v, d in G.edges(data=True):
            label = d.get('label')
            u_label = G.nodes[u].get('label')
            v_label = G.nodes[v].get('label')
            
            if u_label == 'ARGUMENT' and v_label == 'METHOD_PARAMETER_IN':
                arg_to_param += 1
            
            if u_label == 'METHOD_RETURN' and v_label == 'CALL':
                ret_to_call += 1
                
            if label == 'POINTS_TO':
                points_to += 1
                
        log(f"ARGUMENT -> METHOD_PARAMETER_IN: {arg_to_param} (Expect Missing)")
        log(f"METHOD_RETURN -> CALL: {ret_to_call} (Expect Missing)")
        log(f"POINTS_TO Edges: {points_to} (Expect Sparse/Missing)")

        log("\n=== Phase 4: The Property Audit (Fidelity) ===")
        
        nodes_with_line = 0
        nodes_with_code = 0
        nodes_with_type = 0
        
        check_types = ['CALL', 'IDENTIFIER']
        total_checked = 0
        
        for n, d in G.nodes(data=True):
            label = d.get('label')
            if label in check_types:
                total_checked += 1
                if 'LINE_NUMBER' in d and 'COLUMN_NUMBER' in d:
                    nodes_with_line += 1
                if 'CODE' in d:
                    nodes_with_code += 1
                if 'TYPE_FULL_NAME' in d:
                    nodes_with_type += 1
                    
        log(f"Source Mapping (Line/Col): {nodes_with_line}/{total_checked} ({nodes_with_line/total_checked:.2%})")
        log(f"Original Code (CODE): {nodes_with_code}/{total_checked} ({nodes_with_code/total_checked:.2%})")
        log(f"Type Coverage (TYPE_FULL_NAME): {nodes_with_type}/{total_checked} ({nodes_with_type/total_checked:.2%})")
        
        log("\n=== Phase 5: Structural Integrity ===")
        
        orphans = 0
        for n, d in G.nodes(data=True):
            label = d.get('label')
            if label not in ['FILE', 'NAMESPACE_BLOCK', 'META_DATA']: 
                if G.in_degree(n) == 0: 
                    has_incoming_ast = False
                    for pred in G.predecessors(n):
                        edge = G.get_edge_data(pred, n)
                        if edge and edge.get('label') == 'AST':
                            has_incoming_ast = True
                            break
                    if not has_incoming_ast:
                        orphans += 1
                        
        log(f"Orphan Nodes (No incoming AST): {orphans}")
        log(f"Status: {'PASS' if orphans == 0 else 'WARNING'}")
        
        empty_methods = 0
        for n, d in G.nodes(data=True):
            if d.get('label') == 'METHOD':
                has_block = False
                for succ in G.successors(n):
                    edge = G.get_edge_data(n, succ)
                    if edge and edge.get('label') == 'AST': 
                        if G.nodes[succ].get('label') == 'BLOCK':
                            has_block = True
                            break
                if not has_block:
                    if not d.get('IS_EXTERNAL', False):
                        empty_methods += 1
                        
        log(f"Methods without Body (BLOCK): {empty_methods}")
        log(f"Status: {'PASS' if empty_methods == 0 else 'WARNING'}")

if __name__ == "__main__":
    verify_cpg_audit()
