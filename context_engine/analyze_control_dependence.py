import sys
import json
import networkx as nx
from collections import defaultdict
from context_engine import CpgLoader, Slicer

def get_transitive_cdg_predecessors(graph, seed_node):
    """
    Returns all nodes that control-depend on the seed_node (transitively).
    Traverses incoming CDG edges.
    """
    visited = set()
    queue = [seed_node]
    
    while queue:
        curr = queue.pop(0)
        
        # Incoming CDG edges
        for pred in graph.predecessors(curr):
            edge = graph.get_edge_data(pred, curr)
            if edge and edge.get('label') == 'CDG':
                if pred not in visited:
                    visited.add(pred)
                    queue.append(pred)
                    
    return visited

def analyze_control_dependence():
    print("Loading CPG...")
    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    slicer = Slicer(loader)
    
    # Select test candidates (Identifiers with incoming REACHING_DEF)
    print("Selecting test candidates...")
    candidates = []
    identifiers = [n for n, d in G.nodes(data=True) if d.get('label') == 'IDENTIFIER']
    
    count = 0
    for nid in identifiers:
        has_rd = False
        for pred in G.predecessors(nid):
            edge = G.get_edge_data(pred, nid)
            if edge and edge.get('label') == 'REACHING_DEF':
                has_rd = True
                break
        if has_rd:
            candidates.append(nid)
            count += 1
            if count >= 20:
                break
                
    print(f"Selected {len(candidates)} seed nodes.")
    
    print(f"\n{'Seed ID':<10} | {'Method':<15} | {'GT Preds':<8} | {'Slice Preds':<11} | {'Completeness':<12}")
    print("-" * 70)
    
    completeness_scores = []
    
    for seed in candidates:
        method_id = loader.get_method_of_node(seed)
        method_name = "unknown"
        if method_id:
            method_name = G.nodes[method_id].get('NAME', 'unknown')
            
        # 1. Identify Ground Truth Control Predicates (via CDG)
        gt_predicates = get_transitive_cdg_predecessors(G, seed)
        
        if not gt_predicates:
            # No control dependencies (linear code or root)
            # print(f"Skipping {seed}: No CDG predecessors")
            continue
            
        # 2. Generate Slice (Depth=5)
        # We use standard context slice
        slice_nodes, _ = slicer.slice(seed, direction='backward', depth=5, edge_types=['REACHING_DEF', 'CDG', 'REF'])
        
        # 3. Calculate Metrics
        retrieved_preds = 0
        for p in gt_predicates:
            if p in slice_nodes:
                retrieved_preds += 1
                
        completeness = retrieved_preds / len(gt_predicates)
        completeness_scores.append(completeness)
        
        print(f"{seed:<10} | {method_name[:15]:<15} | {len(gt_predicates):<8} | {retrieved_preds:<11} | {completeness:<12.2%}")

    # Summary
    if completeness_scores:
        avg_completeness = sum(completeness_scores) / len(completeness_scores)
        
        print("\n=== Control Dependence Validation Summary ===")
        print(f"Average Control Completeness: {avg_completeness:.2%}")
        
        pass_completeness = avg_completeness >= 0.80
        
        print(f"Pass Criteria (>=80% Transitive): {'PASS' if pass_completeness else 'FAIL'}")
    else:
        print("\nNo valid samples found for control dependence analysis.")

if __name__ == "__main__":
    analyze_control_dependence()
