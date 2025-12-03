import sys
import json
import time
import statistics
from collections import defaultdict
from context_engine import CpgLoader, Slicer

def get_ground_truth(graph, seed_node):
    """
    Computes the transitive closure of REACHING_DEF edges (backward) from the seed_node.
    This represents the "ideal" set of dependencies for data flow.
    """
    visited = set()
    queue = [seed_node]
    visited.add(seed_node)
    
    while queue:
        curr = queue.pop(0)
        
        # Traverse incoming REACHING_DEF edges
        for pred in graph.predecessors(curr):
            edge = graph.get_edge_data(pred, curr)
            if edge and edge.get('label') == 'REACHING_DEF':
                if pred not in visited:
                    visited.add(pred)
                    queue.append(pred)
                    
    return visited

def analyze_def_use_exhaustiveness():
    print("Loading CPG...")
    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    slicer = Slicer(loader)
    
    # Select 20 random identifiers with incoming REACHING_DEF
    # (Reusing logic from analyze_slice_distribution.py for consistency)
    print("Selecting test candidates...")
    candidates = []
    identifiers = [n for n, d in G.nodes(data=True) if d.get('label') == 'IDENTIFIER']
    
    # We want a deterministic set for reproducibility, but random enough to be representative.
    # Let's seed the random number generator if we were using random, but here we'll just take the first 20 
    # that meet the criteria to be simple, or we can use the same logic as before.
    # Let's try to find ones with good depth.
    
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
    
    depths = [1, 2, 3, 5, 7, 10]
    
    # Store aggregate recall per depth
    recall_per_depth = defaultdict(list)
    
    print(f"\n{'Seed ID':<10} | {'GT Size':<8} | " + " | ".join([f"R@{d:<2}" for d in depths]))
    print("-" * (25 + 8 * len(depths)))
    
    for seed in candidates:
        # 1. Compute Ground Truth
        gt_nodes = get_ground_truth(G, seed)
        gt_size = len(gt_nodes)
        
        # Skip trivial cases if any (though we filtered for incoming RD)
        if gt_size <= 1: 
            # If GT is just the node itself, recall is always 100%. 
            # Let's keep it but it might skew averages high.
            pass

        recalls = []
        for d in depths:
            # 2. Compute Slice at Depth d
            # Using standard edge types as per current context engine default or typical usage
            slice_nodes, _ = slicer.slice(seed, direction='backward', depth=d, edge_types=['REACHING_DEF', 'CDG', 'REF'])
            
            # 3. Calculate Recall
            # Intersection of Slice and GT
            # Note: Slice might contain nodes NOT in GT (e.g. CDG/REF nodes). 
            # Recall is fraction of GT retrieved.
            
            retrieved_gt = 0
            for n in slice_nodes:
                if n in gt_nodes:
                    retrieved_gt += 1
            
            recall = retrieved_gt / gt_size if gt_size > 0 else 0
            recalls.append(recall)
            recall_per_depth[d].append(recall)
            
        # Print row
        recall_strs = [f"{r:.2f}" for r in recalls]
        print(f"{seed:<10} | {gt_size:<8} | " + " | ".join(recall_strs))

    # Aggregate Results
    print("\n=== Def-Use Chain Exhaustiveness Summary ===")
    print(f"{'Depth':<6} | {'Avg Recall':<10} | {'Marginal Gain':<15} | {'Status'}")
    print("-" * 50)
    
    prev_recall = 0
    saturation_found = False
    
    for i, d in enumerate(depths):
        avg_recall = statistics.mean(recall_per_depth[d])
        marginal_gain = avg_recall - prev_recall
        
        status = ""
        if not saturation_found:
            if avg_recall >= 0.95:
                status = "PASS (Recall >= 95%)"
                saturation_found = True
            elif i > 0 and marginal_gain < 0.05: # < 5% gain
                status = "SATURATION POINT (< 5% Gain)"
                saturation_found = True
            elif i > 0 and marginal_gain < 0.02: # < 2% gain (diminishing returns)
                 status = "DIMINISHING RETURNS"
        
        print(f"{d:<6} | {avg_recall:<10.2%} | {marginal_gain:<15.2%} | {status}")
        
        prev_recall = avg_recall

if __name__ == "__main__":
    analyze_def_use_exhaustiveness()
