import sys
import time
import random
import statistics
import json
from collections import defaultdict, Counter
from context_engine import CpgLoader, Slicer

def analyze_slice_distribution():
    print("Loading CPG...")
    loader = CpgLoader("libpng_cpg_ddg.json")
    G = loader.load()
    slicer = Slicer(loader)
    
    # Select 20 random identifiers with incoming REACHING_DEF
    print("Selecting 20 random identifiers with incoming REACHING_DEF...")
    candidates = []
    identifiers = [n for n, d in G.nodes(data=True) if d.get('label') == 'IDENTIFIER']
    
    # Shuffle to pick random ones
    random.shuffle(identifiers)
    
    for nid in identifiers:
        has_rd = False
        for pred in G.predecessors(nid):
            edge = G.get_edge_data(pred, nid)
            if edge and edge.get('label') == 'REACHING_DEF':
                has_rd = True
                break
        if has_rd:
            candidates.append(nid)
            if len(candidates) >= 20:
                break
                
    if len(candidates) < 20:
        print(f"Warning: Only found {len(candidates)} identifiers with REACHING_DEF.")
        
    # Test 1.1: Depth vs Size Curve
    print("\n=== Test 1.1: Depth vs Size Curve ===")
    depths = [1, 2, 3, 5, 7, 10]
    results = defaultdict(list)
    
    # Store raw data for Test 1.2
    depth_5_slices = []
    
    print(f"{'Seed ID':<15} | {'Depth':<5} | {'Nodes':<6} | {'Lines':<6} | {'Time(ms)':<8}")
    print("-" * 50)
    
    for seed in candidates:
        seed_data = G.nodes[seed]
        seed_name = seed_data.get('NAME', 'unknown')
        
        for d in depths:
            start_t = time.time()
            # Note: Slicer currently ignores 'edge_types' arg and uses hardcoded logic (REF fallback)
            # We should ideally fix Slicer to use REACHING_DEF if requested.
            # But assuming Slicer uses REF/DDG/REACHING_DEF as available.
            # The current Slicer implementation uses REF fallback if DDG is missing.
            # Since we have DDG (REACHING_DEF), we might need to ensure Slicer uses it.
            # Wait, the Slicer code I saw uses REF fallback logic explicitly.
            # It doesn't seem to use REACHING_DEF directly in the 'slice' method shown in context_engine.py
            # It says: "If DDG is missing, we use REF...".
            # But we HAVE REACHING_DEF now.
            # However, for this analysis, we just run the slicer as is to see its behavior.
            
            slice_nodes, _ = slicer.slice(seed, direction='backward', depth=d)
            duration = (time.time() - start_t) * 1000
            
            # Count unique lines
            unique_lines = set()
            for nid in slice_nodes:
                n = G.nodes[nid]
                if 'LINE_NUMBER' in n:
                    # Need filename to be unique
                    m = loader.get_method_of_node(nid)
                    f = "unknown"
                    if m: f = G.nodes[m].get('FILENAME', 'unknown')
                    unique_lines.add((f, n['LINE_NUMBER']))
            
            results[d].append({
                "nodes": len(slice_nodes),
                "lines": len(unique_lines),
                "time": duration
            })
            
            if d == 5:
                depth_5_slices.append({
                    "seed": seed,
                    "nodes": len(slice_nodes),
                    "lines": len(unique_lines),
                    "files": len(set(f for f, l in unique_lines)),
                    "seed_name": seed_name,
                    "method": loader.get_method_of_node(seed)
                })
                
            print(f"{seed:<15} | {d:<5} | {len(slice_nodes):<6} | {len(unique_lines):<6} | {duration:<8.2f}")

    print("\n--- Depth Analysis Summary ---")
    print(f"{'Depth':<5} | {'Avg Nodes':<10} | {'Avg Lines':<10} | {'Avg Time(ms)':<12}")
    for d in depths:
        avg_nodes = statistics.mean([r['nodes'] for r in results[d]])
        avg_lines = statistics.mean([r['lines'] for r in results[d]])
        avg_time = statistics.mean([r['time'] for r in results[d]])
        print(f"{d:<5} | {avg_nodes:<10.2f} | {avg_lines:<10.2f} | {avg_time:<12.2f}")

    # Test 1.2: Size Distribution Histogram (Depth=5)
    print("\n=== Test 1.2: Size Distribution Histogram (Depth=5) ===")
    bins = {
        "Tiny (1-10)": 0,
        "Small (11-30)": 0,
        "Medium (31-100)": 0,
        "Large (101-500)": 0,
        "Huge (501+)": 0
    }
    
    node_counts = [s['nodes'] for s in depth_5_slices]
    for c in node_counts:
        if c <= 10: bins["Tiny (1-10)"] += 1
        elif c <= 30: bins["Small (11-30)"] += 1
        elif c <= 100: bins["Medium (31-100)"] += 1
        elif c <= 500: bins["Large (101-500)"] += 1
        else: bins["Huge (501+)"] += 1
        
    total = len(depth_5_slices)
    for k, v in bins.items():
        print(f"{k:<15}: {v} ({v/total:.1%})")
        
    print(f"\nStats: Mean={statistics.mean(node_counts):.2f}, Median={statistics.median(node_counts)}, Max={max(node_counts)}")

    # Test 1.3: Outlier Investigation
    print("\n=== Test 1.3: Outlier Investigation ===")
    sorted_slices = sorted(depth_5_slices, key=lambda x: x['nodes'])
    
    print("\nSmallest Slices:")
    for s in sorted_slices[:3]:
        print(f"  Seed {s['seed']} ({s['seed_name']}): {s['nodes']} nodes")
        
    print("\nLargest Slices:")
    for s in sorted_slices[-3:]:
        print(f"  Seed {s['seed']} ({s['seed_name']}): {s['nodes']} nodes")
        # Inspect root cause
        # Check if global
        seed_node = G.nodes[s['seed']]
        is_global = False
        method_id = s['method']
        method_name = "unknown"
        if method_id:
            method_name = G.nodes[method_id].get('NAME', 'unknown')
            if method_name == "<global>": is_global = True
            
        print(f"    Method: {method_name}")
        print(f"    Is Global: {is_global}")
        # Check incoming edges
        in_degree = G.in_degree(s['seed'])
        print(f"    In-Degree: {in_degree}")

if __name__ == "__main__":
    analyze_slice_distribution()
